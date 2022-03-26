FROM python

RUN apt update && apt -y install bluetooth

RUN pip install -U \
    pip \
    setuptools

WORKDIR /project

RUN useradd -m -r user && \
    chown user /project

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

USER user

ENTRYPOINT ["./tbcmd.py", "scan"]
