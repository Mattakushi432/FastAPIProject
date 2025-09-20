FROM ubuntu:latest
LABEL authors="zakrevskyi"

ENTRYPOINT ["top", "-b"]