from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./app.db"
    LLM_BASE_URL: str = "http://localhost:8080"
    LLM_TIMEOUT_SEC: int = 180
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20 MB
    FILES_DIR: str = "/app/data/files"
    SESSION_EXPIRE_HOURS: int = 72
    KALENDER_BASE_URL: str = ""
    KALENDER_FEED_TOKEN: str = ""
    KALENDER_PASSWORD: str = ""
    FEED_TOKEN: str = ""
    KG_INTERNAL_TOKEN: str = ""
    STT_URL: str = ""  # ai-stt /api/stt, z.B. http://host.docker.internal:5003
    # Wenn gesetzt: Bild-Uploads werden vor dem Ablegen entzerrt und zu PDF
    # gewandelt. Erwartet einen Dienst mit /scan, z.B. eine eigene Instanz auf
    # einem Rechner mit Beschleuniger. Leer lassen heisst: das Original-Foto
    # wird abgelegt.
    VISION_SCAN_URL: str = ""
    VISION_SCAN_TIMEOUT: int = 30
    SAGANTA_SESSION_TOKEN: str = ""
    SAGANTA_SESSION_USER: str = "Polylemmata"
    # Mandant aus der Saganta-Anmeldung (app/tenant_auth.py). Der Sub loest
    # mittelfristig SAGANTA_SESSION_TOKEN ab: der meldet naemlich JEDEN Aufrufer
    # als denselben Nutzer an (SAGANTA_SESSION_USER), was mit einem zweiten
    # Konto bedeutet, dass beide dieselbe Post sehen.
    #
    # Bewusst KEIN DEFAULT_OWNER_SUB hier, anders als in kalender/lager/fitness/
    # mealprep. Die Kennung eines konkreten Menschen gehoert nicht in ein Repo,
    # das veroeffentlicht werden soll. Zugeordnet wird mit
    # scripts/postfach-binden.py, einmal und sichtbar.
    POSTFACH_TENANT_SECRET: str = ""
    TENANT_HEADER_ENFORCE: int = 0
    # ★ Bewusst LEER statt einer Adresse aus dem Netz, in dem dieser Dienst
    # entstanden ist. Eine Vorbelegung, die auf einen bestimmten Rechner zeigt,
    # ist fuer jeden anderen falsch, und zwar auf die stille Art: der Dienst
    # startet, die Uebernahme aus Paperless laeuft in einen Timeout, und der
    # Grund steht in keiner Fehlermeldung. Leer heisst: die Funktion ist aus.
    PAPERLESS_PROXY_URL: str = ""
    PAPERLESS_API_TOKEN: str = ""
    PAPERLESS_INTEL_KG_TOKEN: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
