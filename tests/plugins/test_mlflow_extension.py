from pathlib import Path

import mlflow
import numpy as np
import pytest
from sklearn.base import BaseEstimator
from sklearn.linear_model import LinearRegression

from hamilton.plugins.mlflow_extensions import MLFlowModelLoader, MLFlowModelSaver

# TODO move these tests to `plugin_tests` because the required read-writes can get
# complicated and tests are time consuming.


@pytest.fixture
def fitted_sklearn_model() -> BaseEstimator:
    model = LinearRegression()
    model.fit([[0]], [[0]])
    return model


def coefficients_are_equal(model1, model2) -> bool:
    """Check if two linear models have the same coefficients"""
    return np.allclose(model1.coef_, model2.coef_) and np.allclose(
        model1.intercept_, model2.intercept_
    )


def test_mlflow_log_model_to_active_run(fitted_sklearn_model: BaseEstimator, tmp_path: Path):
    model_path = tmp_path / "sklearn_model"
    saver = MLFlowModelSaver(flavor="sklearn")

    mlflow.set_tracking_uri(model_path.as_uri())
    with mlflow.start_run():
        # save model
        metadata = saver.save_data(fitted_sklearn_model)
    # reload model
    loaded_model = mlflow.sklearn.load_model(metadata["model_uri"])

    assert coefficients_are_equal(fitted_sklearn_model, loaded_model)


def test_mlflow_log_model_to_specific_run(fitted_sklearn_model: BaseEstimator, tmp_path: Path):
    model_path = tmp_path / "sklearn_model"
    # create a "previous run"
    mlflow.set_tracking_uri(model_path.as_uri())
    mlflow.start_run()
    run_id = mlflow.active_run().info.run_id
    mlflow.end_run()
    saver = MLFlowModelSaver(flavor="sklearn", run_id=run_id)

    # save model
    metadata = saver.save_data(fitted_sklearn_model)
    # reload model
    loaded_model = mlflow.sklearn.load_model(metadata["model_uri"])

    assert coefficients_are_equal(fitted_sklearn_model, loaded_model)


def test_mlflow_log_model_active_and_specific_run_ids_are_equal(
    fitted_sklearn_model: BaseEstimator, tmp_path: Path
):
    model_path = tmp_path / "sklearn_model"

    mlflow.set_tracking_uri(model_path.as_uri())
    with mlflow.start_run():
        run_id = mlflow.active_run().info.run_id
        saver = MLFlowModelSaver(flavor="sklearn", run_id=run_id)
        # save model
        metadata = saver.save_data(fitted_sklearn_model)
    # reload model
    loaded_model = mlflow.sklearn.load_model(metadata["model_uri"])

    assert coefficients_are_equal(fitted_sklearn_model, loaded_model)


def test_mlflow_log_model_active_and_specific_run_ids_are_unequal(
    fitted_sklearn_model: BaseEstimator, tmp_path: Path
):
    model_path = tmp_path / "sklearn_model"
    mlflow.set_tracking_uri(model_path.as_uri())
    mlflow.start_run()
    run_id = mlflow.active_run().info.run_id
    mlflow.end_run()
    saver = MLFlowModelSaver(flavor="sklearn", run_id=run_id)

    with mlflow.start_run():
        # save model
        with pytest.raises(RuntimeError):
            saver.save_data(fitted_sklearn_model)


def test_mlflow_load_runs_model(fitted_sklearn_model: BaseEstimator, tmp_path: Path):
    mlflow_path = tmp_path / "mlflow_path"
    artifact_path = "model"
    mlflow.set_tracking_uri(mlflow_path.as_uri())
    with mlflow.start_run():
        run_id = mlflow.active_run().info.run_id
        mlflow.sklearn.log_model(fitted_sklearn_model, artifact_path=artifact_path)

    # specify run via model_uri
    loader = MLFlowModelLoader(model_uri=f"runs:/{run_id}/{artifact_path}", flavor="sklearn")
    loaded_model, _ = loader.load_data(LinearRegression)
    assert coefficients_are_equal(fitted_sklearn_model, loaded_model)

    # specify run via arguments
    loader = MLFlowModelLoader(mode="tracking", path=artifact_path, run_id=run_id, flavor="sklearn")
    loaded_model, _ = loader.load_data(LinearRegression)
    assert coefficients_are_equal(fitted_sklearn_model, loaded_model)


def test_mlflow_load_registry_model(fitted_sklearn_model: BaseEstimator, tmp_path: Path):
    mlflow_path = tmp_path / "mlflow_path"
    artifact_path = "model"
    model_name = "my_registered_model"
    version = 1
    # track a model
    mlflow.set_tracking_uri(mlflow_path.as_uri())
    with mlflow.start_run():
        run_id = mlflow.active_run().info.run_id
        mlflow.sklearn.log_model(fitted_sklearn_model, artifact_path=artifact_path)
    # register the model
    run_model_uri = f"runs:/{run_id}/{artifact_path}"
    mlflow.register_model(run_model_uri, model_name)

    # specify via model_uri
    loader = MLFlowModelLoader(model_uri=f"models:/{model_name}/{version}", flavor="sklearn")
    loaded_model, _ = loader.load_data(LinearRegression)
    assert coefficients_are_equal(fitted_sklearn_model, loaded_model)

    # specify via arguments
    loader = MLFlowModelLoader(
        mode="registry", model_name=model_name, version=version, flavor="sklearn"
    )
    loaded_model, _ = loader.load_data(LinearRegression)
    assert coefficients_are_equal(fitted_sklearn_model, loaded_model)


def test_mlflow_infer_flavor(fitted_sklearn_model: BaseEstimator, tmp_path: Path):
    saver = MLFlowModelSaver(path="model")

    metadata = saver.save_data(fitted_sklearn_model)

    assert "sklearn" in metadata["flavors"].keys()


def test_mlflow_handle_saver_kwargs():
    path = "tmp/path"
    flavor = "sklearn"
    saver = MLFlowModelSaver(path=path, flavor=flavor, kwargs=dict(unknown_kwarg=True))

    assert saver.path == path
    assert saver.flavor == flavor
    assert saver.kwargs.get("unknown_kwarg") is True


def test_mlflow_registered_model_metadata(fitted_sklearn_model: BaseEstimator, tmp_path: Path):
    """When registering a model through materializers, the metadata must contain the
    key `registered_model` because the `hamilton.plugins.h_mlflow.MLFlowTracker` is expecting it.
    """
    model_path = tmp_path / "sklearn_model"
    saver = MLFlowModelSaver(flavor="sklearn", register_as="my_model")

    mlflow.set_tracking_uri(model_path.as_uri())
    with mlflow.start_run():
        metadata = saver.save_data(fitted_sklearn_model)

    assert metadata.get("registered_model")
