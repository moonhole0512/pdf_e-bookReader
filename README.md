# E-Book Reader

PDF 기반 전자책과 만화 파일을 한곳에서 관리하고 웹 브라우저로 읽는 가벼운 개인용 서재입니다. Windows 개발 환경과 저사양 Synology NAS를 모두 고려해 Flask, SQLite, pdf.js로 구성했습니다.

## 주요 기능

- PDF 파일 자동 스캔과 서재 동기화
- 브라우저 내 PDF 읽기 및 사용자별 독서 진행률 저장
- Aladin·Google Books 기반 도서 정보 보완과 고해상도 표지 검색
- 표지·저자·장르·ISBN 수동 수정
- 장르를 `소설`, `라이트 노벨`, `만화`, `비문학`, `실용`, `미분류`로 단순화
- 책 제목·저자·시리즈·장르 검색 및 읽기 상태 필터
- 여러 사용자의 독서 상태 분리
- 기존 SQLite 데이터의 자동 마이그레이션
- 마이그레이션이 실제로 필요할 때만 DB 백업 생성
- 저사양 NAS를 위한 Gunicorn 단일 워커 설정

## 요구사항

- Python 3.10 이상 (로컬 실행)
- Docker 및 Docker Buildx (Docker 배포)
- NAS에서 Docker를 실행할 수 있는 환경

## 로컬 실행

가장 간단한 방법은 Windows에서 `run.bat`를 실행하는 것입니다. 스크립트가 `.venv`를 만들고 필요한 패키지를 설치한 뒤 서버를 시작합니다.

브라우저에서 다음 주소를 엽니다.

```text
http://localhost:8000
```

명령줄에서 직접 실행하려면 다음과 같이 합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m waitress --host 0.0.0.0 --port 8000 app:app
```

## 처음 로그인하기

처음 입력한 사용자 이름은 자동으로 생성되며 첫 번째 사용자가 관리자 권한을 갖습니다. 비밀번호를 입력하면 이후 로그인에 사용됩니다.

## 책 파일 추가와 사용법

1. 프로젝트의 `pdfs/` 폴더에 PDF 파일을 넣습니다.
2. 웹 화면에서 `PDF 스캔`을 실행합니다.
3. 새 파일은 스캔 과정에서 도서 정보 보완을 시도합니다.
4. 기존 서가의 누락 정보만 채우려면 `정보 보완`에서 `누락 정보만 보완`을 선택합니다.
5. 전체 정보를 다시 검색해야 할 때만 `전체 서가 다시 가져오기`를 사용합니다. 이 작업은 기존 자동 정보나 수동 수정 내용을 바꿀 수 있습니다.

독서 진행률은 사용자별로 자동 저장됩니다. PDF 파일과 DB를 다른 컴퓨터로 옮길 때는 파일의 상대 경로 구조를 유지하는 것이 안전합니다.

## 데이터와 환경변수

로컬 기본 경로는 다음과 같습니다.

| 항목 | 기본 경로 | 설명 |
|---|---|---|
| 책 파일 | `pdfs/` | 스캔할 PDF 파일 |
| 데이터베이스 | `instance/library.db` | 사용자, 책 정보, 독서 상태 |
| 비밀키 | `instance/.secret_key` | 세션 암호화에 사용 |

`.env` 파일로 다음 값을 재정의할 수 있습니다.

```dotenv
SECRET_KEY=충분히_긴_무작위_문자열
DB_PATH=instance/library.db
PDF_ROOT_PATH=pdfs
```

`instance/`와 `pdfs/`는 Git에 올리지 않도록 무시됩니다. DB를 백업하려면 앱을 중지한 뒤 `instance/` 폴더를 별도로 복사하십시오.

## Docker 이미지 빌드와 Docker Hub 업로드

Docker Hub 로그인 후 프로젝트 루트에서 실행합니다. 예시는 카테고리 UI 변경이 포함된 `1.1.0` 태그입니다.

```powershell
docker login
docker buildx build --platform linux/amd64,linux/arm64/v8 -t gruzam/e-book-reader:1.1.0 -t gruzam/e-book-reader:latest --push .
```

`latest`는 편리한 업데이트용이고, 버전 태그는 문제가 생겼을 때 되돌리기 쉽습니다. 실제 운영 NAS에는 버전 태그를 사용하는 것을 권장합니다.

## NAS에서 처음 실행하기

Synology 예시입니다. 왼쪽 경로는 NAS에서 실제 사용하는 호스트 경로로 바꾸십시오.

```bash
docker run -d --name e-book-reader --restart unless-stopped -p 8000:8000 -v /volume1/docker/e-book-reader/instance:/app/instance -v /volume1/docker/e-book-reader/pdfs:/app/pdfs gruzam/e-book-reader:1.1.0
```

컨테이너 내부 경로는 반드시 유지해야 합니다.

- `instance` → `/app/instance`: DB, 세션 비밀키, 마이그레이션 백업
- `pdfs` → `/app/pdfs`: 실제 전자책 파일

`instance/`와 `pdfs/`를 볼륨으로 연결하지 않으면 컨테이너를 재생성할 때 데이터가 이미지에 포함되지 않아 사라질 수 있습니다.

## NAS에서 업데이트하기

이미지를 새로 올린 뒤 NAS에서 다음 순서로 실행합니다.

```bash
docker pull gruzam/e-book-reader:1.1.0
docker stop e-book-reader
docker rm e-book-reader
docker run -d --name e-book-reader --restart unless-stopped -p 8000:8000 -v /volume1/docker/e-book-reader/instance:/app/instance -v /volume1/docker/e-book-reader/pdfs:/app/pdfs gruzam/e-book-reader:1.1.0
```

기존 컨테이너 이름이나 호스트 경로를 모르면 먼저 확인합니다.

```bash
docker ps -a
docker inspect e-book-reader --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

기존 실행 명령에 별도의 `-e`, 네트워크, 포트 설정이 있었다면 새 `docker run`에도 그대로 유지해야 합니다. 컨테이너만 삭제하려면 `docker rm`을 사용하고, 데이터 볼륨까지 지우는 `docker rm -v`는 사용하지 마십시오.

업데이트 확인:

```bash
docker ps
docker logs --tail=100 e-book-reader
```

이번 버전처럼 DB 구조나 기존 데이터 보완이 포함된 업데이트는 첫 시작 때만 필요한 마이그레이션과 백업을 수행합니다. 이후 재시작에서는 변경 사항이 없으면 백업을 만들지 않습니다.

## 테스트

전체 회귀 테스트:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s _testcode/specs -p "test_*.py"
```

DB 마이그레이션 핵심 테스트:

```powershell
.\.venv\Scripts\python.exe -m unittest _testcode.specs.test_migration
```

외부 도서 API를 사용하는 일부 테스트는 네트워크 상태나 제공자 응답에 영향을 받을 수 있습니다.

## 프로젝트 구조

```text
app.py                  Flask 애플리케이션 진입점
config.py               DB·PDF·세션 설정
models.py               사용자·책·파일·독서 상태 모델
blueprints/             인증·서재·리더·관리 API
services/               스캔·메타데이터·카테고리·마이그레이션
templates/              웹 화면
static/                 CSS와 브라우저 JavaScript
Dockerfile              NAS용 이미지 정의
_testcode/specs/        격리된 테스트 코드
```
