import logging

experiment_logger = logging.getLogger("experiment")

if not experiment_logger.handlers:
    handler = logging.FileHandler(
        "experiment_results.log",
        encoding="utf-8"
    )

    formatter = logging.Formatter("%(asctime)s | %(message)s")
    handler.setFormatter(formatter)

    experiment_logger.addHandler(handler)
    experiment_logger.setLevel(logging.INFO)


def log_exp(msg):
    experiment_logger.info(msg)