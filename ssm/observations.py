import copy
import warnings

import autograd.numpy as np
import autograd.numpy.random as npr
from autograd.scipy.special import gammaln
from autograd.scipy.stats import norm, gamma
from autograd.misc.optimizers import sgd, adam
from autograd import grad

from ssm.util import random_rotation, ensure_args_are_lists, ensure_args_not_none, interpolate_data, logistic, logit


class _Observations(object):
    def __init__(self, K, D, M=0):
        self.K, self.D, self.M = K, D, M

    @property
    def params(self):
        raise NotImplementedError
    
    @params.setter
    def params(self, value):
        raise NotImplementedError

    def permute(self, perm):
        pass
        
    @ensure_args_are_lists
    def initialize(self, datas, inputs=None, masks=None, tags=None):
        pass
        
    def log_prior(self):
        return 0

    def log_likelihoods(self, data, input, mask, tag):
        raise NotImplementedError

    def sample_x(self, z, xhist, input=None, tag=None):
        raise NotImplementedError

    def m_step(self, expectations, datas, inputs, masks, tags, 
               optimizer="adam", num_iters=10, **kwargs):
        """
        If M-step cannot be done in closed form for the transitions, default to SGD.
        """
        optimizer = dict(sgd=sgd, adam=adam)[optimizer]
        
        # expected log joint
        def _expected_log_joint(expectations):
            elbo = self.log_prior()
            for data, input, mask, tag, (expected_states, expected_joints) \
                in zip(datas, inputs, masks, tags, expectations):
                lls = self.log_likelihoods(data, input, mask, tag)
                elbo += np.sum(expected_states * lls)
            return elbo

        # define optimization target
        T = sum([data.shape[0] for data in datas])
        def _objective(params, itr):
            self.params = params
            obj = _expected_log_joint(expectations)
            return -obj / T

        self.params = \
            optimizer(grad(_objective), self.params, num_iters=num_iters, **kwargs)

    def smooth(self, expectations, data, input, tag):
        raise NotImplementedError


class GaussianObservations(_Observations):
    def __init__(self, K, D, M=0):
        super(GaussianObservations, self).__init__(K, D, M)
        self.mus = npr.randn(K, D)
        self.inv_sigmas = -2 + npr.randn(K, D)

    @property
    def params(self):
        return self.mus, self.inv_sigmas
    
    @params.setter
    def params(self, value):
        self.mus, self.inv_sigmas = value

    def permute(self, perm):
        self.mus = self.mus[perm]
        self.inv_sigmas = self.inv_sigmas[perm]
        
    @ensure_args_are_lists
    def initialize(self, datas, inputs=None, masks=None, tags=None):
        # Initialize with KMeans
        from sklearn.cluster import KMeans
        data = np.concatenate(datas)
        km = KMeans(self.K).fit(data)
        self.mus = km.cluster_centers_
        sigmas = np.array([np.var(data[km.labels_ == k], axis=0)
                           for k in range(self.K)])
        self.inv_sigmas = np.log(sigmas + 1e-8)
        
    def log_likelihoods(self, data, input, mask, tag):
        mus, sigmas = self.mus, np.exp(self.inv_sigmas)
        mask = np.ones_like(data, dtype=bool) if mask is None else mask
        return -0.5 * np.sum(
            (np.log(2 * np.pi * sigmas) + (data[:, None, :] - mus)**2 / sigmas) 
            * mask[:, None, :], axis=2)

    def sample_x(self, z, xhist, input=None, tag=None):
        D, mus, sigmas = self.D, self.mus, np.exp(self.inv_sigmas)
        return mus[z] + np.sqrt(sigmas[z]) * npr.randn(D)

    def m_step(self, expectations, datas, inputs, masks, tags, **kwargs):
        x = np.concatenate(datas)
        weights = np.concatenate([Ez for Ez, _ in expectations])
        for k in range(self.K):
            self.mus[k] = np.average(x, axis=0, weights=weights[:,k])
            sqerr = (x - self.mus[k])**2
            self.inv_sigmas[k] = np.log(np.average(sqerr, weights=weights[:,k], axis=0))

    def smooth(self, expectations, data, input, tag):
        """
        Compute the mean observation under the posterior distribution
        of latent discrete states.
        """
        return expectations.dot(self.mus)


class StudentsTObservations(_Observations):
    def __init__(self, K, D, M=0):
        super(StudentsTObservations, self).__init__(K, D, M)
        self.mus = npr.randn(K, D)
        self.inv_sigmas = -2 + npr.randn(K, D)
        # Student's t distribution also has a degrees of freedom parameter
        self.inv_nus = np.log(4) * np.ones(K)

    @property
    def params(self):
        return self.mus, self.inv_sigmas, self.inv_nus
    
    @params.setter
    def params(self, value):
        self.mus, self.inv_sigmas, self.inv_nus = value

    def permute(self, perm):
        self.mus = self.mus[perm]
        self.inv_sigmas = self.inv_sigmas[perm]
        self.inv_nus = self.inv_nus[perm] 
        
    @ensure_args_are_lists
    def initialize(self, datas, inputs=None, masks=None, tags=None):
        # Initialize with KMeans
        from sklearn.cluster import KMeans
        data = np.concatenate(datas)
        km = KMeans(self.K).fit(data)
        self.mus = km.cluster_centers_
        sigmas = np.array([np.var(data[km.labels_ == k], axis=0)
                           for k in range(self.K)])
        self.inv_sigmas = np.log(sigmas + 1e-8)
        self.inv_nus = np.log(4) * np.ones(self.K)
        
    def log_likelihoods(self, data, input, mask, tag):
        D, mus, sigmas, nus = self.D, self.mus, np.exp(self.inv_sigmas), np.exp(self.inv_nus)
        # mask = np.ones_like(data, dtype=bool) if mask is None else mask

        resid = data[:, None, :] - mus
        z = resid / sigmas
        return -0.5 * (nus + D) * np.log(1.0 + (resid * z).sum(axis=2) / nus) + \
            gammaln((nus + D) / 2.0) - gammaln(nus / 2.0) - D / 2.0 * np.log(nus) \
            -D / 2.0 * np.log(np.pi) - 0.5 * np.sum(np.log(sigmas), axis=1)

    def sample_x(self, z, xhist, input=None, tag=None):
        D, mus, sigmas, nus = self.D, self.mus, np.exp(self.inv_sigmas), np.exp(self.inv_nus)
        tau = npr.gamma(nus[z] / 2.0, 2.0 / nus[z])
        return mus[z] + np.sqrt(sigmas[z] / tau) * npr.randn(D)

    def smooth(self, expectations, data, input, tag):
        """
        Compute the mean observation under the posterior distribution
        of latent discrete states.
        """
        return expectations.dot(self.mus)


class BernoulliObservations(_Observations):
    def __init__(self, K, D, M=0):
        super(BernoulliObservations, self).__init__(K, D, M)
        self.logit_ps = npr.randn(K, D)
        
    @property
    def params(self):
        return (self.logit_ps,)
    
    @params.setter
    def params(self, value):
        self.logit_ps = value
        
    def permute(self, perm):
        self.logit_ps = self.logit_ps[perm]
        
    @ensure_args_are_lists
    def initialize(self, datas, inputs=None, masks=None, tags=None):
        
        # Initialize with KMeans
        from sklearn.cluster import KMeans
        data = np.concatenate(datas)
        km = KMeans(self.K).fit(data)
        ps = km.cluster_centers_
        assert np.all((ps > 0) & (ps < 1))
        self.logit_ps = np.log(ps / (1-ps))
        
    def log_likelihoods(self, data, input, mask, tag):
        assert data.dtype == int and data.min() >= 0 and data.max() <= 1
        ps = 1 / (1 + np.exp(self.logit_ps))
        mask = np.ones_like(data, dtype=bool) if mask is None else mask
        lls = data[:, None, :] * np.log(ps) + (1 - data[:, None, :]) * np.log(1 - ps)
        return np.sum(lls * mask[:, None, :], axis=2)

    def sample_x(self, z, xhist, input=None, tag=None):
        ps = 1 / (1 + np.exp(self.logit_ps))
        return npr.rand(self.D) < ps[z]

    def m_step(self, expectations, datas, inputs, masks, tags, **kwargs):
        x = np.concatenate(datas)
        weights = np.concatenate([Ez for Ez, _ in expectations])
        for k in range(self.K):
            ps = np.average(x, axis=0, weights=weights[:,k])
            self.logit_ps[k] = np.log((ps + 1e-8) / (1 - ps + 1e-8))

    def smooth(self, expectations, data, input, tag):
        """
        Compute the mean observation under the posterior distribution
        of latent discrete states.
        """
        ps = 1 / (1 + np.exp(self.logit_ps))
        return expectations.dot(ps)


class PoissonObservations(_Observations):
    def __init__(self, K, D, M=0):
        super(PoissonObservations, self).__init__(K, D, M)
        self.log_lambdas = npr.randn(K, D)
        
    @property
    def params(self):
        return (self.log_lambdas,)
    
    @params.setter
    def params(self, value):
        self.log_lambdas = value
        
    def permute(self, perm):
        self.log_lambdas = self.log_lambdas[perm]
        
    @ensure_args_are_lists
    def initialize(self, datas, inputs=None, masks=None, tags=None):
        
        # Initialize with KMeans
        from sklearn.cluster import KMeans
        data = np.concatenate(datas)
        km = KMeans(self.K).fit(data)
        self.log_lambdas = np.log(km.cluster_centers_)
        
    def log_likelihoods(self, data, input, mask, tag):
        assert data.dtype == int
        lambdas = np.exp(self.inv_lambdas)
        mask = np.ones_like(data, dtype=bool) if mask is None else mask
        lls = -gammaln(data[:,None,:] + 1) -lambdas + data[:,None,:] * np.log(lambdas)
        return np.sum(lls * mask[:, None, :], axis=2)

    def sample_x(self, z, xhist, input=None, tag=None):
        lambdas = np.exp(self.inv_lambdas)
        return npr.poisson(lambdas[z])

    def m_step(self, expectations, datas, inputs, masks, tags, **kwargs):
        x = np.concatenate(datas)
        weights = np.concatenate([Ez for Ez, _ in expectations])
        for k in range(self.K):
            self.inv_lambdas = np.log(np.average(x, axis=0, weights=weights[:,k]) + 1e-8)

    def smooth(self, expectations, data, input, tag):
        """
        Compute the mean observation under the posterior distribution
        of latent discrete states.
        """
        return expectations.dot(np.exp(self.inv_lambdas))


class AutoRegressiveObservations(_Observations):
    def __init__(self, K, D, M=0):
        super(AutoRegressiveObservations, self).__init__(K, D, M)
        
        # Distribution over initial point
        self.mu_init = np.zeros(D)
        self.inv_sigma_init = np.zeros(D)
        
        # AR parameters
        self.As = .95 * np.array([random_rotation(D) for _ in range(K)])
        self.bs = npr.randn(K, D)
        self.Vs = npr.randn(K, D, M)
        self.inv_sigmas = -4 + npr.randn(K, D)

    @property
    def params(self):
        return self.As, self.bs, self.Vs, self.inv_sigmas
        
    @params.setter
    def params(self, value):
        self.As, self.bs, self.Vs, self.inv_sigmas = value
        
    def permute(self, perm):
        self.As = self.As[perm]
        self.bs = self.bs[perm]
        self.Vs = self.Vs[perm]
        self.inv_sigmas = self.inv_sigmas[perm]

    def initialize(self, datas, inputs=None, masks=None, tags=None):
        # Initialize with linear regressions
        from sklearn.linear_model import LinearRegression
        data = np.concatenate(datas) 
        input = np.concatenate(inputs)
        T = data.shape[0]

        for k in range(self.K):
            ts = npr.choice(T-1, replace=False, size=T//2)
            x, y = np.column_stack((data[ts], input[ts])), data[ts+1]
            lr = LinearRegression().fit(x, y)
            self.As[k] = lr.coef_[:, :self.D]
            self.Vs[k] = lr.coef_[:, self.D:]
            self.bs[k] = lr.intercept_
            
            resid = y - lr.predict(x)
            sigmas = np.var(resid, axis=0)
            self.inv_sigmas[k] = np.log(sigmas + 1e-8)
        
    def _compute_mus(self, data, input, mask, tag):
        assert np.all(mask), "ARHMM cannot handle missing data"

        As, bs, Vs = self.As, self.bs, self.Vs

        # linear function of preceding data, current input, and bias
        mus = np.matmul(As[None, ...], data[:-1, None, :, None])[:, :, :, 0]
        mus = mus + np.matmul(Vs[None, ...], input[1:, None, :, None])[:, :, :, 0]
        mus = mus + bs

        # Pad with the initial condition
        mus = np.concatenate((self.mu_init * np.ones((1, self.K, self.D)), mus))
        return mus

    def log_likelihoods(self, data, input, mask, tag):
        mus = self._compute_mus(data, input, mask, tag)
        sigmas = np.exp(self.inv_sigmas)
        return -0.5 * np.sum(
            (np.log(2 * np.pi * sigmas) + (data[:, None, :] - mus)**2 / sigmas) 
            * mask[:, None, :], axis=2)

    def m_step(self, expectations, datas, inputs, masks, tags, **kwargs):
        from sklearn.linear_model import LinearRegression
        D, M = self.D, self.M

        for k in range(self.K):
            xs, ys, weights = [], [], []
            for (Ez, _), data, input in zip(expectations, datas, inputs):
                xs.append(np.hstack((data[:-1], input[:-1])))
                ys.append(data[1:])
                weights.append(Ez[1:,k])
            xs = np.concatenate(xs)
            ys = np.concatenate(ys)
            weights = np.concatenate(weights)

            # Fit a weighted linear regression
            lr = LinearRegression()
            lr.fit(xs, ys, sample_weight=weights)
            self.As[k], self.Vs[k], self.bs[k] = lr.coef_[:,:D], lr.coef_[:,D:], lr.intercept_

            # Update the variances
            yhats = lr.predict(xs)
            sqerr = (ys - yhats)**2
            self.inv_sigmas[k] = np.log(np.average(sqerr, weights=weights, axis=0))
        
    def sample_x(self, z, xhist, input=None, tag=None):
        D, As, bs, sigmas = self.D, self.As, self.bs, np.exp(self.inv_sigmas)
        if xhist.shape[0] == 0:
            mu_init = self.mu_init
            sigma_init = np.exp(self.inv_sigma_init)
            return mu_init + np.sqrt(sigma_init) * npr.randn(D)
        else:
            return As[z].dot(xhist[-1]) + bs[z] + np.sqrt(sigmas[z]) * npr.randn(D)

    def smooth(self, expectations, data, input, tag):
        """
        Compute the mean observation under the posterior distribution
        of latent discrete states.
        """
        T = expectations.shape[0]
        mask = np.ones((T, self.D), dtype=bool) 
        mus = self._compute_mus(data, input, mask, tag)
        return (expectations[:, :, None] * mus).sum(1)


# Robust autoregressive models with Student's t noise
class RobustAutoRegressiveObservations(AutoRegressiveObservations):
    def __init__(self, K, D, M=0):
        super(RobustAutoRegressiveObservations, self).__init__(K, D, M)
        self.inv_nus = np.log(4) * np.ones(K)

    @property
    def params(self):
        return self.As, self.bs, self.Vs, self.inv_sigmas, self.inv_nus
        
    @params.setter
    def params(self, value):
        self.As, self.bs, self.Vs, self.inv_sigmas, self.inv_nus = value

    def permute(self, perm):
        super(RobustAutoRegressiveObservations, self).permute(perm)
        self.inv_nus = self.inv_nus[perm]

    def log_likelihoods(self, data, input, mask, tag):
        D = self.D
        mus = self._compute_mus(data, input, mask, tag)
        sigmas = np.exp(self.inv_sigmas)
        nus = np.exp(self.inv_nus)

        resid = data[:, None, :] - mus
        z = resid / sigmas
        return -0.5 * (nus + D) * np.log(1.0 + (resid * z).sum(axis=2) / nus) + \
            gammaln((nus + D) / 2.0) - gammaln(nus / 2.0) - D / 2.0 * np.log(nus) \
            -D / 2.0 * np.log(np.pi) - 0.5 * np.sum(np.log(sigmas), axis=1)

    def sample_x(self, z, xhist, input=None, tag=None):
        D, As, bs, sigmas, nus = self.D, self.As, self.bs, np.exp(self.inv_sigmas), np.exp(self.inv_nus)
        if xhist.shape[0] == 0:
            mu_init = self.mu_init
            sigma_init = np.exp(self.inv_sigma_init)
            return mu_init + np.sqrt(sigma_init) * npr.randn(D)
        else:
            tau = npr.gamma(nus[z] / 2.0, 2.0 / nus[z])
            return As[z].dot(xhist[-1]) + bs[z] + np.sqrt(sigmas[z] / tau) * npr.randn(D)


class _RecurrentAutoRegressiveObservationsMixin(AutoRegressiveObservations):
    """
    A simple mixin to allow for smarter initialization.
    """
    def initialize(self, datas, inputs=None, masks=None, tags=None):
        data = np.concatenate(datas) 
        input = np.concatenate(inputs)
        T = data.shape[0]
    
        from sklearn.cluster import KMeans
        km = KMeans(self.K)
        km.fit(data)
        z = km.labels_[:-1]

        # Cluster the data before initializing
        from sklearn.linear_model import LinearRegression
        
        for k in range(self.K):
            ts = np.where(z == k)[0]
            x, y = np.column_stack((data[ts], input[ts])), data[ts+1]
            lr = LinearRegression().fit(x, y)
            self.As[k] = lr.coef_[:, :self.D]
            self.Vs[k] = lr.coef_[:, self.D:]
            self.bs[k] = lr.intercept_
            
            resid = y - lr.predict(x)
            sigmas = np.var(resid, axis=0)
            self.inv_sigmas[k] = np.log(sigmas + 1e-8)
            assert np.all(np.isfinite(self.inv_sigmas))



class RecurrentAutoRegressiveObservations(
    _RecurrentAutoRegressiveObservationsMixin, 
    AutoRegressiveObservations):
    pass


class RecurrentRobustAutoRegressiveObservations(
    _RecurrentAutoRegressiveObservationsMixin, 
    RobustAutoRegressiveObservations):
    pass


class DiagonalAutoRegressiveObservations(_Observations):
    """
    Special case of an AR model in which the output dimensions
    do not interact.  They just independently evolve with a switching
    drive determined by a shared underlying discrete state. 

    x_{td} = a_d x_{t-1, d} + b_d + noise

    where a_d in [0,1] for d = 1, ..., D

    """
    def __init__(self, K, D, M=0, fp_max=4):
        super(DiagonalAutoRegressiveObservations, self).__init__(K, D, M)
        
        # Distribution over initial point
        self.mu_init = np.zeros(D)
        self.inv_sigma_init = np.zeros(D)
        
        # AR parameters
        assert fp_max > 0
        self.fp_max = fp_max
        self.logit_fixed_points = npr.randn(K, D)
        
        self.inv_taus = npr.randn(K, D)
        
        self.Vs = npr.randn(K, D, M)
        self.inv_sigmas = -4 + npr.randn(K, D)

    @property
    def params(self):
        return self.logit_fixed_points, self.inv_taus, self.Vs, self.inv_sigmas
        
    @params.setter
    def params(self, value):
        self.logit_fixed_points, self.inv_taus, self.Vs, self.inv_sigmas = value

    @property
    def fixed_points(self):
        return -self.fp_max + 2 * self.fp_max * logistic(self.logit_fixed_points)

    @property
    def taus(self):
        return 1 + np.exp(self.inv_taus)
        
    @property
    def As(self):
        return 1 - 1 / self.taus

    @property
    def bs(self):
        return self.fixed_points / self.taus

    def log_prior(self):
        # return np.sum(norm.logpdf(self.fixed_points, 0, 1)) + \
        #        np.sum(gamma.logpdf((self.taus - 1) / 10, 1))
        # return np.sum(gamma.logpdf((self.taus - 1) / 10, 1))
        return 0

    def permute(self, perm):
        self.logit_fixed_points = self.fixed_points[perm]
        self.inv_taus = self.inv_taus[perm]
        self.Vs = self.Vs[perm]
        self.inv_sigmas = self.inv_sigmas[perm]

    def initialize(self, datas, inputs=None, masks=None, tags=None):
        data = np.concatenate(datas) 
        input = np.concatenate(inputs)
        T = data.shape[0]
    
        from sklearn.cluster import KMeans
        km = KMeans(self.K)
        km.fit(data)
        z = km.labels_[:-1]

        # Cluster the data before initializing
        from sklearn.linear_model import LinearRegression
        
        for k in range(self.K):
            ts = np.where(z == k)[0]

            for d in range(self.D):
                x, y = np.column_stack((data[ts, d], input[ts], np.ones_like(ts))), data[ts+1, d]
                w, sumsq, _, _ = np.linalg.lstsq(x, y, rcond=None)
                
                # Set tau via As[k, d]
                a_kd = np.clip(w[0], 1e-4, 1-1e-4)
                tau_kd = 1 / (1 - a_kd)
                self.inv_taus[k, d] = np.log(tau_kd - 1)
                # tau_kd = np.clip(tau_kd, 1+1e-2, self.tau_max - 1 - 1e-2)
                # self.logit_taus[k, d] = logit((tau_kd - 1) / self.tau_max)

                # Set the fixed point via b
                fp_kd = w[-1] * tau_kd
                fp_kd = np.clip(fp_kd, -self.fp_max + 1e-2, self.fp_max - 1e-2)
                self.logit_fixed_points[k, d] = logit((self.fp_max + fp_kd) / (2 * self.fp_max))

                # Set the input drive
                self.Vs[k, d] = w[1:-1]
                
                # Set the observation noise
                self.inv_sigmas[k, d] = np.log(sumsq / len(ts) + 1e-8)

            assert np.all(np.isfinite(self.inv_sigmas))
        
    def _compute_mus(self, data, input, mask, tag):
        assert np.all(mask), "ARHMM cannot handle missing data"
        As, bs, Vs = self.As, self.bs, self.Vs

        # linear function of preceding data, current input, and bias
        mus = As[None, :, :] * data[:-1, None, :] 
        mus = mus + np.matmul(Vs[None, ...], input[1:, None, :, None])[:, :, :, 0]
        mus = mus + bs

        # Pad with the initial condition
        mus = np.concatenate((self.mu_init * np.ones((1, self.K, self.D)), mus))
        return mus

    def log_likelihoods(self, data, input, mask, tag):
        mus = self._compute_mus(data, input, mask, tag)
        sigmas = np.exp(self.inv_sigmas)
        return -0.5 * np.sum(
            (np.log(2 * np.pi * sigmas) + (data[:, None, :] - mus)**2 / sigmas) 
            * mask[:, None, :], axis=2)

    # def m_step(self, expectations, datas, inputs, masks, tags, **kwargs):
    #     from sklearn.linear_model import LinearRegression
    #     D, M = self.D, self.M

    #     us, xs, ys = [], [], []
    #     for data, input in zip(datas, inputs):
    #         us.append(input[:-1])
    #         xs.append(data[:-1])
    #         ys.append(data[1:])
    #     us = np.concatenate(us)
    #     xs = np.concatenate(xs)
    #     ys = np.concatenate(ys)
    #     T = ys.shape[0]
        
    #     for k in range(self.K):
    #         weights = np.concatenate([Ez[1:,k] for Ez, _ in expectations])
            
    #         # Fit a weighted linear regression
    #         # for d in range(self.D):
    #         #     if weights.sum() > .1:
    #         #         Xd = np.sqrt(weights)[:,None] * np.column_stack((xs[:, d], us, np.ones(T)))
    #         #         yd = np.sqrt(weights) * ys[:, d]

    #         #         w, sumsq, _, _ = np.linalg.lstsq(Xd, yd, rcond=None)
    #         #         self.logit_As[k, d] = logit(np.clip(w[0], 1e-4, 1-1e-4))
    #         #         self.Vs[k, d] = w[1:-1]
    #         #         self.bs[k, d] = w[-1]
    #         #         self.inv_sigmas[k, d] = np.log(sumsq / T + 1e-8)
    #         #     else:
    #         #         pass
    #         #     assert np.all(np.isfinite(self.inv_sigmas))

    #         # Fit a weighted linear regression
    #         from sklearn.linear_model import LinearRegression
    #         lr = LinearRegression()
    #         lr.fit(np.hstack((xs, us)), ys, sample_weight=weights)
    #         self.logit_As[k] = logit(np.clip(np.diag(lr.coef_[:,:D]), 1e-4, 1-1e-4))
    #         self.Vs[k] = lr.coef_[:,D:]
    #         self.bs[k] = lr.intercept_
            
        
    def sample_x(self, z, xhist, input=None, tag=None):
        D, As, bs, sigmas = self.D, self.As, self.bs, np.exp(self.inv_sigmas)
        if xhist.shape[0] == 0:
            mu_init = self.mu_init
            sigma_init = np.exp(self.inv_sigma_init)
            return mu_init + np.sqrt(sigma_init) * npr.randn(D)
        else:
            return As[z] * xhist[-1] + bs[z] + np.sqrt(sigmas[z]) * npr.randn(D)

    def smooth(self, expectations, data, input, tag):
        """
        Compute the mean observation under the posterior distribution
        of latent discrete states.
        """
        T = expectations.shape[0]
        mask = np.ones((T, self.D), dtype=bool) 
        mus = self._compute_mus(data, input, mask, tag)
        return (expectations[:, :, None] * mus).sum(1)
