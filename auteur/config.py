"""Runtime configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # DashScope / Alibaba Cloud
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    # Model identifiers
    model_director: str = "qwen-max"
    model_writer: str = "qwen-plus"
    model_critic: str = "qwen-vl-max"
    model_image: str = "wanx2.1-t2i-turbo"
    model_i2v: str = "wan2.1-i2v-turbo"
    model_t2v: str = "wan2.1-t2v-turbo"

    # Pipeline tuning
    critic_threshold: float = 0.7
    max_shot_attempts: int = 3
    parallel_shot_limit: int = 3

    # Job polling
    job_poll_interval: float = 10.0   # seconds between polls
    job_timeout: float = 600.0        # max seconds to wait for one job

    # Storage
    project_dir: str = "./projects"
    output_dir: str = "./output"


settings = Settings()
