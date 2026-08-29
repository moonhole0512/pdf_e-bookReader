# Python 3.10 Slim 버전을 기본 이미지로 사용합니다.
# Slim 이미지는 더 작고 보안에 유리합니다.
FROM python:3.10-slim

# 컨테이너 내부의 작업 디렉터리를 /app으로 설정합니다.
# 모든 명령은 이 디렉터리를 기준으로 실행됩니다.
WORKDIR /app

# 호스트의 requirements.txt 파일을 컨테이너의 /app 디렉터리로 복사합니다.
COPY requirements.txt .

# Python 종속성을 설치합니다.
# --no-cache-dir 옵션은 pip 캐시를 사용하지 않아 이미지 크기를 줄입니다.
RUN pip install --no-cache-dir -r requirements.txt

# .env 파일에 설정된 PDF_ROOT_PATH를 컨테이너 내부 경로로 설정합니다.
# 이 경로는 이미지 빌드 시 컨테이너 내부로 복사될 pdfs 디렉터리의 경로입니다.
ENV PDF_ROOT_PATH=/app/pdfs

# .env 파일에 설정된 DB_PATH를 컨테이너 내부 경로로 설정합니다.
# 이 경로는 볼륨 마운트를 통해 호스트의 instance 디렉터리와 연결될 것입니다.
# ENV DB_PATH=instance/library.db
ENV DB_PATH=/app/instance/library.db

# .dockerignore에 명시된 파일을 제외하고, 현재 디렉터리의 모든 파일을
# 컨테이너의 /app 디렉터리로 복사합니다.
COPY . .

# 애플리케이션이 8000번 포트에서 수신 대기함을 Docker에 알립니다.
# 이는 문서화 목적이며, 실제 포트 매핑은 'docker run' 명령에서 이루어집니다.
EXPOSE 8000

# 컨테이너가 시작될 때 실행될 기본 명령을 정의합니다.
# 이 명령은 Flask 애플리케이션을 실행합니다.
CMD ["gunicorn", "-c", "gunicorn_config.py", "app:app"]
