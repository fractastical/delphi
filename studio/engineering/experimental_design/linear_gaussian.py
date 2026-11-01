"""Bounded linear-Gaussian design calculations; no observed responses are needed."""
from __future__ import annotations

import math

import numpy as np


def _array(value, name, ndim):
    result = np.asarray(value, dtype=float)
    if result.ndim != ndim or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite {ndim}-D numeric array")
    return result


def _positive_definite(value, name, size):
    matrix = _array(value, name, 2)
    if matrix.shape != (size, size):
        raise ValueError(f"{name} must have shape {(size, size)}")
    if not np.allclose(matrix, matrix.T, rtol=1e-10, atol=1e-12):
        raise ValueError(f"{name} must be symmetric")
    matrix = (matrix + matrix.T) / 2
    try:
        np.linalg.cholesky(matrix)
    except np.linalg.LinAlgError as exc:
        raise ValueError(f"{name} must be positive definite") from exc
    return matrix


def _positive_semidefinite(value, name, size):
    matrix = _array(value, name, 2)
    if matrix.shape != (size, size):
        raise ValueError(f"{name} must have shape {(size, size)}")
    if not np.allclose(matrix, matrix.T, rtol=1e-10, atol=1e-12):
        raise ValueError(f"{name} must be symmetric")
    matrix = (matrix + matrix.T) / 2
    if float(np.linalg.eigvalsh(matrix)[0]) < -1e-10:
        raise ValueError(f"{name} must be positive semidefinite")
    return matrix


def posterior_covariance(prior_covariance, sensitivity, noise_covariance):
    """Return prospective covariance after y=H theta+epsilon, epsilon~N(0,R).

    This update uses no response values. Repeated rows are independent only when
    callers explicitly put the corresponding joint errors in ``noise_covariance``.
    """
    prior = _array(prior_covariance, "prior_covariance", 2)
    if prior.shape[0] != prior.shape[1] or prior.shape[0] == 0:
        raise ValueError("prior_covariance must be a nonempty square matrix")
    prior = _positive_semidefinite(prior, "prior_covariance", prior.shape[0])
    h = _array(sensitivity, "sensitivity", 2)
    if h.shape[1] != prior.shape[0] or h.shape[0] == 0:
        raise ValueError("sensitivity must have one nonempty row per declared observation")
    noise = _positive_definite(noise_covariance, "noise_covariance", h.shape[0])
    # Kalman covariance update. Solve rather than invert the predictive covariance.
    cross = prior @ h.T
    predictive = h @ cross + noise
    updated = prior - cross @ np.linalg.solve(predictive, cross.T)
    updated = (updated + updated.T) / 2
    # Roundoff may make a tiny negative eigenvalue; materially invalid output is an error.
    smallest = float(np.linalg.eigvalsh(updated)[0])
    if smallest < -1e-10:
        raise ArithmeticError("posterior covariance lost positive semidefiniteness")
    return updated


def rank_diagnostics(sensitivity, noise_covariance):
    """Return normalized likelihood rank and a basis for unidentifiable directions."""
    h = _array(sensitivity, "sensitivity", 2)
    if h.shape[0] == 0 or h.shape[1] == 0:
        raise ValueError("sensitivity must have at least one observation and parameter")
    noise = _positive_definite(noise_covariance, "noise_covariance", h.shape[0])
    whitened = np.linalg.solve(np.linalg.cholesky(noise), h)
    _, singular_values, vh = np.linalg.svd(whitened, full_matrices=True)
    tolerance = (max(whitened.shape) * np.finfo(float).eps * singular_values[0]
                 if singular_values.size else 0.0)
    rank = int(np.sum(singular_values > tolerance))
    null = vh[rank:, :].T
    return {"rank": rank, "parameter_count": int(h.shape[1]), "full_rank": rank == h.shape[1],
            "singular_values": singular_values.tolist(),
            "nullspace_basis": null.T.tolist(), "whitened_sensitivity": whitened.tolist()}


def evaluate_design(prior_covariance, sensitivity, noise_covariance, target, cost):
    """Evaluate expected target-variance reduction per explicitly declared cost.

    In a linear-Gaussian model the posterior covariance is independent of the
    response value, so the prospective covariance update equals its expectation
    under the stated model. ``target`` must be dimensionless or have one declared
    unit shared by its components.
    """
    prior = _array(prior_covariance, "prior_covariance", 2)
    if prior.shape[0] != prior.shape[1] or prior.shape[0] == 0:
        raise ValueError("prior_covariance must be a nonempty square matrix")
    prior = _positive_semidefinite(prior, "prior_covariance", prior.shape[0])
    h = _array(sensitivity, "sensitivity", 2)
    target_vector = _array(target, "target", 1)
    if target_vector.shape != (prior.shape[0],):
        raise ValueError("target must have one coefficient per dimensionless parameter")
    if isinstance(cost, bool) or not math.isfinite(float(cost)) or cost <= 0:
        raise ValueError("cost must be positive and finite")
    posterior = posterior_covariance(prior, h, noise_covariance)
    prior_variance = float(target_vector @ prior @ target_vector)
    posterior_variance = float(target_vector @ posterior @ target_vector)
    reduction = prior_variance - posterior_variance
    tolerance = 1e-10 * max(1.0, abs(prior_variance))
    if reduction < -tolerance:
        raise ArithmeticError("conditioning increased target variance")
    reduction = max(0.0, reduction)
    noise = _positive_definite(noise_covariance, "noise_covariance", h.shape[0])
    sign_r, logdet_r = np.linalg.slogdet(noise)
    sign_s, logdet_s = np.linalg.slogdet(noise + h @ prior @ h.T)
    if sign_r <= 0 or sign_s <= 0:
        raise ArithmeticError("expected information covariance is not positive definite")
    return {
        "prior_covariance": prior.tolist(),
        "expected_posterior_covariance": posterior.tolist(),
        "target_prior_variance": prior_variance,
        "expected_target_posterior_variance": posterior_variance,
        "expected_target_variance_reduction": reduction,
        "cost": float(cost),
        "expected_target_variance_reduction_per_cost": reduction / float(cost),
        "expected_information_nats": 0.5 * float(logdet_s - logdet_r),
        "identifiability": rank_diagnostics(h, noise),
        "observation_count": int(h.shape[0]),
        "parameter_count": int(h.shape[1]),
        "measurement_rows": [],
    }

