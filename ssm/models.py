from ssm.core import BaseHMM, BaseHSMM, BaseLDS, BaseSwitchingLDS

from ssm.init_state_distns import InitialStateDistribution

from ssm.transitions import \
    StationaryTransitions, \
    StickyTransitions, \
    InputDrivenTransitions, \
    RecurrentTransitions, \
    RecurrentOnlyTransitions, \
    RBFRecurrentTransitions, \
    NeuralNetworkRecurrentTransitions, \
    NegativeBinomialSemiMarkovTransitions

from ssm.observations import \
    GaussianObservations, \
    DiagonalGaussianObservations, \
    BernoulliObservations, \
    PoissonObservations, \
    VonMisesObservations, \
    CategoricalObservations, \
    MultivariateStudentsTObservations, \
    StudentsTObservations, \
    AutoRegressiveObservations, \
    AutoRegressiveDiagonalNoiseObservations, \
    IndependentAutoRegressiveObservations, \
    RobustAutoRegressiveObservations, \
    RobustAutoRegressiveDiagonalNoiseObservations

from ssm.emissions import \
    GaussianEmissions, \
    GaussianOrthogonalEmissions, \
    GaussianIdentityEmissions, \
    GaussianNeuralNetworkEmissions, \
    StudentsTEmissions, \
    StudentsTOrthogonalEmissions, \
    StudentsTIdentityEmissions, \
    StudentsTNeuralNetworkEmissions, \
    BernoulliEmissions, \
    BernoulliOrthogonalEmissions, \
    BernoulliIdentityEmissions, \
    BernoulliNeuralNetworkEmissions, \
    PoissonEmissions, \
    PoissonOrthogonalEmissions, \
    PoissonIdentityEmissions, \
    PoissonNeuralNetworkEmissions, \
    AutoRegressiveEmissions, \
    AutoRegressiveOrthogonalEmissions, \
    AutoRegressiveIdentityEmissions, \
    AutoRegressiveNeuralNetworkEmissions


def HMM(num_states,
        observation_dim,
        input_dim=0,
        transitions="standard",
        transition_kwargs=None,
        observations="gaussian",
        observation_kwargs=None,
        **kwargs):
    """
    Construct an HMM object with the appropriate observations
    and dynamics.

    :param K: number of discrete latent states
    :param D: observation dimension
    :param M: input dimension
    :param observations: conditional distribution of the data
    :param recurrent: whether or not past observations influence transitions probabilities.
    :param recurrent_only: if true, _only_ the past observations influence transitions.
    """

    # Make the initial state distribution
    init_state_distn = InitialStateDistribution(
        num_states, observation_dim, input_dim=input_dim)

    # Make the transition model
    transition_classes = dict(
        standard=StationaryTransitions,
        stationary=StationaryTransitions,
        sticky=StickyTransitions,
        inputdriven=InputDrivenTransitions,
        recurrent=RecurrentTransitions,
        recurrent_only=RecurrentOnlyTransitions,
        rbf_recurrent=RBFRecurrentTransitions,
        nn_recurrent=NeuralNetworkRecurrentTransitions
        )
    if transitions not in transition_classes:
        raise Exception("Invalid transition model: {}. Must be one of {}".
            format(transitions, list(transition_classes.keys())))

    transition_class = transition_classes[transitions]
    transition_kwargs = transition_kwargs or {}
    transition_distn = transition_class(
        num_states, observation_dim, input_dim=input_dim, **transition_kwargs)

    # This is the master list of observation classes.
    # When you create a new observation class, add it here.
    observation_classes = dict(
        gaussian=GaussianObservations,
        diagonal_gaussian=DiagonalGaussianObservations,
        studentst=MultivariateStudentsTObservations,
        t=MultivariateStudentsTObservations,
        diagonal_t=StudentsTObservations,
        diagonal_studentst=StudentsTObservations,
        bernoulli=BernoulliObservations,
        categorical=CategoricalObservations,
        poisson=PoissonObservations,
        vonmises=VonMisesObservations,
        ar=AutoRegressiveObservations,
        autoregressive=AutoRegressiveObservations,
        diagonal_ar=AutoRegressiveDiagonalNoiseObservations,
        diagonal_autoregressive=AutoRegressiveDiagonalNoiseObservations,
        independent_ar=IndependentAutoRegressiveObservations,
        robust_ar=RobustAutoRegressiveObservations,
        robust_autoregressive=RobustAutoRegressiveObservations,
        diagonal_robust_ar=RobustAutoRegressiveDiagonalNoiseObservations,
        diagonal_robust_autoregressive=RobustAutoRegressiveDiagonalNoiseObservations,
        )

    observations = observations.lower()
    if observations not in observation_classes:
        raise Exception("Invalid observation model: {}. Must be one of {}".
            format(observations, list(observation_classes.keys())))

    observation_class = observation_classes[observations]
    observation_kwargs = observation_kwargs or {}
    observation_distn = observation_class(
        num_states, observation_dim, input_dim=input_dim, **observation_kwargs)

    # Make the HMM
    return BaseHMM(num_states, observation_dim,
                   init_state_distn, transition_distn, observation_distn,
                   input_dim=input_dim)



def HSMM(K, D, M=0,
         transitions="nb",
         transition_kwargs=None,
         observations="gaussian",
         observation_kwargs=None,
         **kwargs):
    """
    Construct an hidden semi-Markov model (HSMM) object with the appropriate observations
    and dynamics.

    :param K: number of discrete latent states
    :param D: observation dimension
    :param M: input dimension
    :param observations: conditional distribution of the data
    :param recurrent: whether or not past observations influence transitions probabilities.
    :param recurrent_only: if true, _only_ the past observations influence transitions.
    """

    # Make the initial state distribution
    init_state_distn = InitialStateDistribution(K, D, M=M)

    # Make the transition model
    transition_classes = dict(
        nb=NegativeBinomialSemiMarkovTransitions,
        )
    if transitions not in transition_classes:
        raise Exception("Invalid transition model: {}. Must be one of {}".
            format(transitions, list(transition_classes.keys())))

    transition_kwargs = transition_kwargs or {}
    transition_distn = transition_classes[transitions](K, D, M=M, **transition_kwargs)

    # This is the master list of observation classes.
    # When you create a new observation class, add it here.
    observation_classes = dict(
        gaussian=GaussianObservations,
        diagonal_gaussian=DiagonalGaussianObservations,
        studentst=MultivariateStudentsTObservations,
        t=MultivariateStudentsTObservations,
        diagonal_t=StudentsTObservations,
        diagonal_studentst=StudentsTObservations,
        bernoulli=BernoulliObservations,
        categorical=CategoricalObservations,
        poisson=PoissonObservations,
        vonmises=VonMisesObservations,
        ar=AutoRegressiveObservations,
        autoregressive=AutoRegressiveObservations,
        diagonal_ar=AutoRegressiveDiagonalNoiseObservations,
        diagonal_autoregressive=AutoRegressiveDiagonalNoiseObservations,
        independent_ar=IndependentAutoRegressiveObservations,
        robust_ar=RobustAutoRegressiveObservations,
        robust_autoregressive=RobustAutoRegressiveObservations,
        diagonal_robust_ar=RobustAutoRegressiveDiagonalNoiseObservations,
        diagonal_robust_autoregressive=RobustAutoRegressiveDiagonalNoiseObservations,
        )

    observations = observations.lower()
    if observations not in observation_classes:
        raise Exception("Invalid observation model: {}. Must be one of {}".
            format(observations, list(observation_classes.keys())))

    observation_kwargs = observation_kwargs or {}
    observation_distn = observation_classes[observations](K, D, M=M, **observation_kwargs)

    # Make the HMM
    return BaseHSMM(K, D, M, init_state_distn, transition_distn, observation_distn)


def SLDS(N, K, D, M=0,
         transitions="standard",
         transition_kwargs=None,
         hierarchical_transition_tags=None,
         dynamics="gaussian",
         dynamics_kwargs=None,
         hierarchical_dynamics_tags=None,
         emissions="gaussian",
         emission_kwargs=None,
         hierarchical_emission_tags=None,
         single_subspace=True,
         **kwargs):
    """
    Construct an SLDS object with the appropriate observations, latent states, and dynamics.

    :param N: observation dimension
    :param K: number of discrete latent states
    :param D: latent dimension
    :param M: input dimension
    :param observations: conditional distribution of the data
    :param robust_dynamics: if true, continuous latent states have Student's t noise.
    :param recurrent: whether or not past observations influence transitions probabilities.
    :param recurrent_only: if true, _only_ the past observations influence transitions.
    :param single_subspace: if true, all discrete states share the same mapping from
        continuous latent states to observations.
    """
    # Make the initial state distribution
    init_state_distn = InitialStateDistribution(K, D, M=M)

    # Make the transition model
    transition_classes = dict(
        standard=StationaryTransitions,
        stationary=StationaryTransitions,
        sticky=StickyTransitions,
        inputdriven=InputDrivenTransitions,
        recurrent=RecurrentTransitions,
        recurrent_only=RecurrentOnlyTransitions,
        rbf_recurrent=RBFRecurrentTransitions,
        nn_recurrent=NeuralNetworkRecurrentTransitions
        )

    transitions = transitions.lower()
    if transitions not in transition_classes:
        raise Exception("Invalid transition model: {}. Must be one of {}".
                        format(transitions, list(transition_classes.keys())))

    transition_kwargs = transition_kwargs or {}
    transition_distn = transition_classes[transitions](K, D, M=M, **transition_kwargs)

    # Make the dynamics distn
    dynamics_classes = dict(
        none=GaussianObservations,
        gaussian=AutoRegressiveObservations,
        t=RobustAutoRegressiveObservations,
        studentst=RobustAutoRegressiveObservations,
        )

    dynamics = dynamics.lower()
    if dynamics not in dynamics_classes:
        raise Exception("Invalid dynamics model: {}. Must be one of {}".
                        format(dynamics, list(dynamics_classes.keys())))

    dynamics_kwargs = dynamics_kwargs or {}
    dynamics_distn = dynamics_classes[dynamics](K, D, M=M, **dynamics_kwargs)

    # Make the emission distn
    emission_classes = dict(
        gaussian=GaussianEmissions,
        gaussian_orthog=GaussianOrthogonalEmissions,
        gaussian_id=GaussianIdentityEmissions,
        gaussian_nn=GaussianNeuralNetworkEmissions,
        studentst=StudentsTEmissions,
        studentst_orthog=StudentsTOrthogonalEmissions,
        studentst_id=StudentsTIdentityEmissions,
        studentst_nn=StudentsTNeuralNetworkEmissions,
        t=StudentsTEmissions,
        t_orthog=StudentsTOrthogonalEmissions,
        t_id=StudentsTIdentityEmissions,
        t_nn=StudentsTNeuralNetworkEmissions,
        poisson=PoissonEmissions,
        poisson_orthog=PoissonOrthogonalEmissions,
        poisson_id=PoissonIdentityEmissions,
        poisson_nn=PoissonNeuralNetworkEmissions,
        bernoulli=BernoulliEmissions,
        bernoulli_orthog=BernoulliOrthogonalEmissions,
        bernoulli_id=BernoulliIdentityEmissions,
        bernoulli_nn=BernoulliNeuralNetworkEmissions,
        ar=AutoRegressiveEmissions,
        ar_orthog=AutoRegressiveOrthogonalEmissions,
        ar_id=AutoRegressiveIdentityEmissions,
        ar_nn=AutoRegressiveNeuralNetworkEmissions,
        autoregressive=AutoRegressiveEmissions,
        autoregressive_orthog=AutoRegressiveOrthogonalEmissions,
        autoregressive_id=AutoRegressiveIdentityEmissions,
        autoregressive_nn=AutoRegressiveNeuralNetworkEmissions
        )

    emissions = emissions.lower()
    if emissions not in emission_classes:
        raise Exception("Invalid emission model: {}. Must be one of {}".
                        format(emissions, list(emission_classes.keys())))

    emission_kwargs = emission_kwargs or {}
    emission_distn = emission_classes[emissions](N, K, D, M=M, single_subspace=single_subspace, **emission_kwargs)

    # Make the HMM
    return BaseSwitchingLDS(N, K, D, M, init_state_distn, transition_distn, dynamics_distn, emission_distn)


def LDS(N, D, M=0,
        dynamics="gaussian",
        dynamics_kwargs=None,
        hierarchical_dynamics_tags=None,
        emissions="gaussian",
        emission_kwargs=None,
        hierarchical_emission_tags=None,
        **kwargs):
    """
    Construct an LDS object with the appropriate observations, latent states, and dynamics.
    Currently, this uses a lot of the same code path as the SLDS.

    :param N: observation dimension
    :param D: latent dimension
    :param M: input dimension
    :param observations: conditional distribution of the data
    :param robust_dynamics: if true, continuous latent states have Student's t noise.
    """
    # Make the dynamics distn
    dynamics_classes = dict(
        gaussian=AutoRegressiveObservations,
        t=RobustAutoRegressiveObservations,
        studentst=RobustAutoRegressiveObservations,
        )

    dynamics = dynamics.lower()
    if dynamics not in dynamics_classes:
        raise Exception("Invalid dynamics model: {}. Must be one of {}".
                        format(dynamics, list(dynamics_classes.keys())))

    dynamics_kwargs = dynamics_kwargs or {}
    dynamics_distn = dynamics_classes[dynamics](1, D, M=M, **dynamics_kwargs)

    # Make the emission distn
    emission_classes = dict(
        gaussian=GaussianEmissions,
        gaussian_orthog=GaussianOrthogonalEmissions,
        gaussian_id=GaussianIdentityEmissions,
        gaussian_nn=GaussianNeuralNetworkEmissions,
        studentst=StudentsTEmissions,
        studentst_orthog=StudentsTOrthogonalEmissions,
        studentst_id=StudentsTIdentityEmissions,
        studentst_nn=StudentsTNeuralNetworkEmissions,
        t=StudentsTEmissions,
        t_orthog=StudentsTOrthogonalEmissions,
        t_id=StudentsTIdentityEmissions,
        t_nn=StudentsTNeuralNetworkEmissions,
        poisson=PoissonEmissions,
        poisson_orthog=PoissonOrthogonalEmissions,
        poisson_id=PoissonIdentityEmissions,
        poisson_nn=PoissonNeuralNetworkEmissions,
        bernoulli=BernoulliEmissions,
        bernoulli_orthog=BernoulliOrthogonalEmissions,
        bernoulli_id=BernoulliIdentityEmissions,
        bernoulli_nn=BernoulliNeuralNetworkEmissions,
        ar=AutoRegressiveEmissions,
        ar_orthog=AutoRegressiveOrthogonalEmissions,
        ar_id=AutoRegressiveIdentityEmissions,
        ar_nn=AutoRegressiveNeuralNetworkEmissions,
        autoregressive=AutoRegressiveEmissions,
        autoregressive_orthog=AutoRegressiveOrthogonalEmissions,
        autoregressive_id=AutoRegressiveIdentityEmissions,
        autoregressive_nn=AutoRegressiveNeuralNetworkEmissions
        )

    emissions = emissions.lower()
    if emissions not in emission_classes:
        raise Exception("Invalid emission model: {}. Must be one of {}".
                        format(emissions, list(emission_classes.keys())))

    emission_kwargs = emission_kwargs or {}
    emission_distn = emission_classes[emissions](N, 1, D, M=M, **emission_kwargs)


    # Make the HMM
    return BaseLDS(N, D, M, dynamics_distn, emission_distn)
