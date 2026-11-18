# ocr-text-basic

증빙 PDF나 사진을 PaddleOCR-VL 1.6으로 읽어서 쪽마다 글 줄만 담은 JSON을 만든다. 신원 값은 번호를 붙인 `[가림#1]`로 가리고 원래 값은 별도 파일로 낸다. LLM과 외부 API는 부르지 않는다.

## 출력

```json
{
 "document": {"doc_id": "document"},
 "pages": [
  {
   "page": 1,
   "text": [
    "등록금 납부 내역서",
    "학번 [가림#1]",
    "학기 : 2024학년도 제1학기",
    "구분 | 항목 | 금액",
    "등록금 | 수업료(등록금) | 2,360,000",
    "교육지원비 | 650,000"
   ]
  }
 ]
}
```

- `document.doc_id`는 `--doc-id`로 준 값이다. 주지 않으면 첫 파일 이름에서 확장자를 뺀 값이다.
- `pages[].page`는 1부터 센 쪽 번호다. PDF는 PDF 쪽마다 한 쪽이고 사진은 파일마다 한 쪽이다.
- `pages[].text`는 읽은 순서대로 놓은 줄 목록이다.
  - 글 블록은 줄바꿈마다 한 줄이다.
  - 표 블록은 표 한 행이 한 줄이다. 그 행에서 시작하는 칸의 글을 왼쪽부터 ` | `로 잇는다.
  - 어느 칸이 머리글인지는 판단하지 않는다.
- 가린 자리는 `[가림#번호]` 하나다. 한 줄이나 한 표 칸 안에서 이어진 가린 낱말은 한 번호로 묶는다. 번호는 문서 전체에서 읽은 순서대로 1부터 센다.

## 가린 값 파일

`--masked-out`을 주면 번호마다 원래 값과 가린 이유를 별도 파일에 쓴다. Jev 코드가 신청자와 같은 사람인지 확인하거나 날짜를 읽을 때 쓴다.

```json
{
 "document": {"doc_id": "document"},
 "masked": [
  {"id": 1, "page": 1, "value": ": 202435982", "reason": "shape", "shape": "digits"},
  {"id": 2, "page": 1, "value": "모의새봄", "reason": "application", "field": "student_name"},
  {"id": 3, "page": 1, "value": ": 모의하늘", "reason": "label", "label": "담당"}
 ]
}
```

| reason | 뜻 | 함께 오는 키 |
| --- | --- | --- |
| `application` | 신청 정보의 값과 같다 | `field`: 신청 정보 키 |
| `shape` | 신원 값 모양이다 | `shape`: `rrn` `phone` `email` `digits`(8자리 이상 숫자) |
| `label` | 이름표 뒤 값이다 | `label`: 이름표 낱말 |
| `institution` | 기관 이름 모양이다 | 없음 |

한 번호에 이유가 여럿이면 `application` `shape` `label` `institution` 순서로 앞의 것 하나를 적는다. 값은 읽은 글 그대로이고 `:` 같은 앞뒤 글자도 들어 있다.

**이 파일은 LLM에 넣지 않는다.** 원래 신원 값이 들어 있다. LLM에는 출력 JSON만 넣고 이 파일은 코드만 읽는다. Git에도 넣지 않는다.

## 설치

Python 3.12에서 확인했다.

```bash
python3.12 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

처음 실행할 때 PaddleOCR가 모델을 내려받는다.

### Mac에서 MLX 서버로 돌리기

Apple Silicon Mac에서는 MLX 빌드를 서버로 띄워서 쓰는 쪽이 빠르다. 서버는 별도 가상환경에 설치한다. 확인한 버전은 mlx-vlm 0.7.12다.

```bash
python3.12 -m venv .mlx && .mlx/bin/pip install mlx-vlm==0.7.12
```

```bash
.mlx/bin/mlx_vlm.server --host 127.0.0.1 --port 8111 --trust-remote-code --model <PaddleOCR-VL-1.6 MLX 모델 폴더>
```

## 실행

```bash
.venv/bin/python -m ocr_text_basic 증빙.pdf -o out.json --masked-out masked.json
```

Mac MLX 서버를 쓸 때는 다음과 같다.

```bash
.venv/bin/python -m ocr_text_basic 증빙.pdf -o out.json --server http://127.0.0.1:8111/ --server-model <서버가 띄운 모델 이름>
```

여러 장 사진이 한 서류이면 쪽 순서대로 파일을 나열한다.

```bash
.venv/bin/python -m ocr_text_basic 1쪽.jpg 2쪽.jpg --doc-id 서류1 -o out.json
```

| 옵션 | 뜻 |
| --- | --- |
| `-o` | 출력 JSON 경로. 없으면 화면에 쓴다 |
| `--doc-id` | 문서 번호 |
| `--masked-out` | 가린 값 파일 경로. 위 가린 값 파일 절을 본다 |
| `--applicant` | 신청 정보 JSON. 아래 가림 절을 본다 |
| `--server` `--server-model` | PaddleOCR-VL을 띄운 서버 주소와 모델 이름 |
| `--models-dir` | 미리 받아 둔 PP-DocLayoutV3가 있는 폴더 |
| `--raw-out` | 리더 원본 기록도 저장한다. 가리지 않은 글이 들어 있다 |
| `--from-raw` | 저장한 리더 원본 기록에서 출력만 다시 만든다. 모델을 부르지 않는다 |

## 가림

두 겹으로 가린다.

1. 신청 정보로 준 값과 신원 값 모양을 가린다. 신원 값 모양은 주민등록번호와 휴대폰 번호와 이메일과 8자리 이상 숫자다. 사업자등록번호 모양과 구분자가 있는 날짜는 제외한다.
2. `ocr_text_basic/profiles/student_aid.yaml`의 이름표 뒤 값을 가린다. 예를 들어 성명과 학번과 문서번호와 발급 뒤 값이다. 금액과 날짜와 학기 같은 낱말은 남긴다.

신청 정보는 `--applicant`로 준다. 키는 `student_name` `student_id` `birth_date` `applicant_name` `employee_id` `phone` `account_number` `address` `email`과 `birth_date`로 끝나는 키를 쓴다. `applicant.example.json`을 참고한다.

```json
{"student_name": "모의새봄", "student_id": "20240001", "birth_date": "2005-03-12"}
```

신청 정보를 주지 않아도 2번과 1번의 모양 규칙은 동작한다. 다만 이름표 없이 따로 적힌 이름은 신청 정보 없이 가려지지 않는다.

## 알려진 한계

- 이름표 뒤를 넓게 가린다. `학번 : 202435982`는 `학번 [가림#1]`이 되고 가린 값에 `:`도 들어간다. 문서번호와 발급 뒤 값은 신원 값이 아니어도 가려진다. 원래 값은 가린 값 파일에 있다.
- 표에서 여러 행에 걸친 칸은 첫 행 줄에만 나온다. 위 예에서 `교육지원비 | 650,000` 줄에는 `등록금`이 다시 나오지 않는다.
- 글 줄만 낸다. 값마다 머리글을 붙이는 표 출력은 이 저장소에 없다.
- 위 버전 조합으로 Mac MLX 서버 경로만 확인했다. PaddleOCR 기본 실행 방식과 Windows와 Linux와 새 가상환경 설치는 확인하지 않았다.

## 테스트

모델 없이 돈다.

```bash
.venv/bin/python -m unittest discover -s tests
```
