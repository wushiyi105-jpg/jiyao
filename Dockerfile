FROM python:3.10-slim

LABEL org.opencontainers.image.source="https://github.com/wushiyi105-jpg/jiyao"
LABEL org.opencontainers.image.description="纪要 · 会议:从转写抽决议、待办、悬置,出一封可直发的跟进邮件"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY . .

RUN pip install -e .

EXPOSE 8000

CMD ["python", "-m", "jiyao", "web", "--host", "0.0.0.0"]
