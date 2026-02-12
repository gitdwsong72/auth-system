# Git Workflow

## 브랜치 전략

### 기본 브랜치
- `master`: 프로덕션 배포 브랜치 (GitLab에서만 병합)
- `develop`: 개발 통합 브랜치 (테스트 환경)

### 작업 브랜치
```bash
# JIRA 티켓 기반 브랜치 (필수 형식)
SKTL-XXXX

# 예시
SKTL-1234
SKTL-5678
```

> **중요**: 모든 작업 브랜치는 `SKTL-XXXX` 형식을 따릅니다. (JIRA 티켓 ID)

---

## 워크플로우

```
┌─────────────────────────────────────────────────────────────────┐
│                         워크플로우 흐름                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. master에서 브랜치 생성                                        │
│     master ──────► SKTL-XXXX                                    │
│                                                                 │
│  2. 개발 완료 후 develop에 MR                                     │
│     SKTL-XXXX ───► develop (테스트 환경)                         │
│                                                                 │
│  3. 테스트 완료 후 GitLab에서 master로 MR                          │
│     SKTL-XXXX ───► master (GitLab에서만!)                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1. 작업 브랜치 생성

```bash
# master 최신화
git checkout master
git pull origin master

# JIRA 티켓 기반 브랜치 생성
git checkout -b SKTL-1234
```

### 2. 개발 작업

```bash
# 작업 수행 후 커밋
git add .
git commit -m "feat(user): 사용자 목록 페이지 추가"

# 원격에 푸시
git push -u origin SKTL-1234
```

### 3. 개발 환경 테스트 (develop 병합)

```bash
# GitLab에서 MR 생성
# Source: SKTL-1234
# Target: develop

# MR 승인 후 develop에 병합
# → 개발 환경에서 테스트 수행
```

### 4. 운영 배포 (master 병합)

```bash
# 테스트 완료 후 GitLab에서 MR 생성
# Source: SKTL-1234
# Target: master

# ⚠️ 주의: 로컬에서 master로 병합/푸시 금지!
# 반드시 GitLab MR을 통해서만 병합
```

---

## 로컬 master 보호

### Git Hook 설정 (pre-push)

로컬에서 master로의 push를 방지하는 hook을 설정합니다.

```bash
# .git/hooks/pre-push
#!/bin/bash

protected_branch='master'
current_branch=$(git symbolic-ref HEAD | sed -e 's,.*/\(.*\),\1,')

if [ $current_branch = $protected_branch ]; then
    echo "❌ 오류: master 브랜치에 직접 push할 수 없습니다."
    echo "GitLab MR을 통해 병합해주세요."
    exit 1
fi

# master로의 push 시도 감지
while read local_ref local_sha remote_ref remote_sha; do
    if [[ "$remote_ref" == *"$protected_branch"* ]]; then
        echo "❌ 오류: master 브랜치에 직접 push할 수 없습니다."
        echo "GitLab MR을 통해 병합해주세요."
        exit 1
    fi
done

exit 0
```

```bash
# Hook 실행 권한 부여
chmod +x .git/hooks/pre-push
```

---

## 병합 전략

### develop 병합
- **Squash Merge** 권장
- 깔끔한 커밋 히스토리 유지
- MR 단위로 하나의 커밋

### master 병합 (GitLab)
- **Merge Commit** 사용
- 릴리즈 히스토리 추적 용이
- 배포 이력 관리

---

## 충돌 해결

```bash
# 최신 master 가져오기
git fetch origin
git rebase origin/master

# 충돌 해결 후
git add .
git rebase --continue

# 본인 브랜치에 강제 푸시
git push --force-with-lease
```

---

## 유용한 명령어

```bash
# 작업 임시 저장
git stash
git stash pop

# 커밋 메시지 수정
git commit --amend

# 마지막 N개 커밋 정리
git rebase -i HEAD~N

# 브랜치 정리
git branch -d SKTL-1234
git remote prune origin

# 브랜치 목록 확인
git branch -a
```

---

## 주의사항

### 금지 사항
1. **로컬에서 master push 금지**: GitLab MR을 통해서만 병합
2. **로컬에서 master merge 금지**: 작업 브랜치에서 직접 master 병합 금지
3. **force push 주의**: 공유 브랜치(develop, master)에는 사용 금지

### 권장 사항
1. **커밋 전 확인**: `git diff --staged`로 변경사항 확인
2. **작은 단위 커밋**: 하나의 목적당 하나의 커밋
3. **의미 있는 커밋 메시지**: 컨벤션 준수 (feat, fix, refactor 등)
4. **정기적인 rebase**: master 변경사항을 주기적으로 반영

---

## 브랜치 생명주기

```
1. 생성: master에서 SKTL-XXXX 브랜치 생성
2. 개발: 로컬에서 개발 및 커밋
3. 테스트: develop에 MR → 개발 환경 테스트
4. 배포: GitLab에서 master로 MR → 운영 배포
5. 정리: 병합 완료 후 브랜치 삭제
```

```bash
# 병합 완료 후 로컬 브랜치 삭제
git branch -d SKTL-1234

# 원격 브랜치 삭제 (필요시)
git push origin --delete SKTL-1234
```
