from modelOS_spec.use_cases.services import (
    backup_service,
    emulator_execution_service,
    microservices,
    real_time_mxe_service,
)
import modelOS_spec.infrastructure.adapters as adapters
from modelOS_spec.infrastructure.credentials import config

orchestrator = adapters.PrefectWorkflowEngineAdapter()


def deploy_backup_service():
    orchestrator.deploy(
        github_repo_name="modelOS_spec",
        flow_path="src/modelOS_spec/use_cases/services/backup_service.py:run",
        docker_image_name=f"{config.DockerConfigsCreds.DOCKER_HUB_USERNAME.value}/backup_service",
        docker_image_tag="latest",
        docker_file_path="DynamicBuild",
        workflow=backup_service.run,
        # schedule=timedelta(days=3),
    )


def deploy_emulator_service():
    orchestrator.deploy(
        github_repo_name="modelOS_spec",
        flow_path="src/modelOS_spec/use_cases/services/emulator_execution_service.py:run",
        docker_image_name=f"{config.DockerConfigsCreds.DOCKER_HUB_USERNAME.value}/emulator_execution_service",
        docker_image_tag="latest",
        docker_file_path="DynamicBuild",
        workflow=emulator_execution_service.run,
        # schedule=timedelta(minutes=30),
    )


def deploy_microservices():
    orchestrator.deploy(
        github_repo_name="modelOS_spec",
        flow_path="src/modelOS_spec/use_cases/services/microservices.py:run",
        docker_image_name=f"{config.DockerConfigsCreds.DOCKER_HUB_USERNAME.value}/microservices",
        docker_image_tag="latest",
        docker_file_path="DynamicBuild",
        workflow=microservices.run,
        # schedule=timedelta(minutes=15),
    )


def deploy_real_time_mxe_service():
    orchestrator.deploy(
        github_repo_name="modelOS_spec",
        flow_path="src/modelOS_spec/use_cases/services/real_time_mxe_service.py:run",
        docker_image_name=f"{config.DockerConfigsCreds.DOCKER_HUB_USERNAME.value}/real_time_mxe_service",
        docker_image_tag="latest",
        docker_file_path="DynamicBuild",
        workflow=real_time_mxe_service.run,
        # schedule=timedelta(minutes=5),
    )


if __name__ == "__main__":
    deploy_backup_service()
    deploy_emulator_service()
    deploy_microservices()
    deploy_real_time_mxe_service()
    
