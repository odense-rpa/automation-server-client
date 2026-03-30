import os
from dotenv import load_dotenv


class AutomationServerConfig:
    token: str = ""
    url: str = ""
    session: str | None = None
    resource: str | None = None
    process: str | None = None

    workqueue_override: int | None = None

    @staticmethod
    def init_from_environment():
        load_dotenv()

        AutomationServerConfig.url = (
            os.environ["ATS_URL"] if "ATS_URL" in os.environ else ""
        )
        AutomationServerConfig.token = (
            os.environ["ATS_TOKEN"] if "ATS_TOKEN" in os.environ else ""
        )
        AutomationServerConfig.session = os.environ.get("ATS_SESSION")
        AutomationServerConfig.resource = os.environ.get("ATS_RESOURCE")
        AutomationServerConfig.process = os.environ.get("ATS_PROCESS")

        # Convert workqueue_override to int if present
        workqueue_override_str = os.environ.get("ATS_WORKQUEUE_OVERRIDE")
        AutomationServerConfig.workqueue_override = (
            int(workqueue_override_str) if workqueue_override_str else None
        )

        if AutomationServerConfig.url == "":
            raise ValueError("ATS_URL is not set in the environment")

    @staticmethod
    def auth_headers() -> dict:
        """Return Authorization header dict, or empty dict if no token is configured."""
        if AutomationServerConfig.token:
            return {"Authorization": f"Bearer {AutomationServerConfig.token}"}
        return {}
