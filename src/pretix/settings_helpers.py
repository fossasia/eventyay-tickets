def build_db_tls_config(config, db_backend):
    db_ssl_mode = config.get("database", "sslmode", fallback="disable")
    # add postgresql TLS options
    if db_ssl_mode != "disable" and db_backend == "postgresql":
        db_tls_config = {
            "sslmode": db_ssl_mode,
            "sslrootcert": config.get("database", "sslrootcert"),
        }
        # add postgresql mTLS options
        if config.has_option("database", "sslcert"):
            db_tls_config["sslcert"] = config.get("database", "sslcert")
            db_tls_config["sslkey"] = config.get("database", "sslkey")
        return db_tls_config
    return None


def build_redis_tls_config(config):
    redis_ssl_cert_reqs = config.get("redis", "ssl_cert_reqs", fallback="none")
    # add redis tls options
    if redis_ssl_cert_reqs != "none":
        redis_tls_config = {
            "ssl_cert_reqs": redis_ssl_cert_reqs,
            "ssl_ca_certs": config.get("redis", "ssl_ca_certs"),
        }
        # add redis mTLS options
        if config.has_option("redis", "ssl_certfile"):
            redis_tls_config["ssl_keyfile"] = config.get("redis", "ssl_keyfile")
            redis_tls_config["ssl_certfile"] = config.get("redis", "ssl_certfile")
        return redis_tls_config
    return None
