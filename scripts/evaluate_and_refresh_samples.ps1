$ErrorActionPreference = 'Stop'

$base = 'http://127.0.0.1:8000'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pdfPaths = @(
  (Join-Path $repoRoot 'data/pdfs/peblo_pdf_grade1_math_numbers.pdf'),
  (Join-Path $repoRoot 'data/pdfs/peblo_pdf_grade3_science_plants_animals.pdf'),
  (Join-Path $repoRoot 'data/pdfs/peblo_pdf_grade4_english_grammar.pdf')
)

function Poll-SourceReady {
  param(
    [string]$BaseUrl,
    [string]$SourceId,
    [int]$MaxAttempts = 80,
    [int]$DelayMs = 500
  )

  for ($i = 0; $i -lt $MaxAttempts; $i++) {
    $detail = Invoke-RestMethod -Method GET -Uri "$BaseUrl/v1/sources/$SourceId"
    if ($detail.status -eq 'ready' -or $detail.status -eq 'failed') {
      return $detail
    }
    Start-Sleep -Milliseconds $DelayMs
  }

  throw "Source $SourceId did not reach ready/failed in time."
}

function Predict-McqChoice {
  param(
    [object[]]$Options,
    [string]$Explanation,
    [bool]$ShouldBeCorrect
  )

  $predictedCorrect = $null
  if ($Explanation) {
    $predictedCorrect = $Options | Where-Object {
      $optionText = "$($_.text)"
      $optionText.Length -gt 0 -and $Explanation.ToLower().Contains($optionText.ToLower())
    } | Select-Object -First 1
  }
  if ($null -eq $predictedCorrect) {
    $predictedCorrect = $Options | Where-Object { $_.text -notmatch 'rejects|unrelated|opposite' } | Select-Object -First 1
  }
  if ($null -eq $predictedCorrect) {
    $predictedCorrect = $Options[0]
  }

  if ($ShouldBeCorrect) {
    return $predictedCorrect.id
  }

  $wrong = $Options | Where-Object { $_.id -ne $predictedCorrect.id } | Select-Object -First 1
  if ($null -eq $wrong) {
    return $predictedCorrect.id
  }
  return $wrong.id
}

function Predict-TrueFalseValue {
  param(
    [string]$Explanation,
    [bool]$ShouldBeCorrect
  )

  $predicted = $true
  if ($Explanation) {
    $text = $Explanation.ToLower()
    if ($text.Contains('false') -and -not $text.Contains('true')) {
      $predicted = $false
    }
  }

  if ($ShouldBeCorrect) {
    return $predicted
  }
  return -not $predicted
}

$health = Invoke-RestMethod -Method GET -Uri "$base/health"

$ingestedSources = @()
foreach ($pdfPath in $pdfPaths) {
  $fileName = [System.IO.Path]::GetFileName($pdfPath)
  $raw = curl.exe -s -X POST "$base/v1/sources" -F "title=$fileName" -F "file=@$pdfPath;type=application/pdf"
  $createResponse = $raw | ConvertFrom-Json
  $sourceDetail = Poll-SourceReady -BaseUrl $base -SourceId $createResponse.id

  $ingestedSources += [PSCustomObject]@{
    file = $fileName
    create_response = $createResponse
    source_detail = $sourceDetail
  }
}

$primarySource = $ingestedSources[0].source_detail
$primarySourceId = "$($primarySource.id)"

$adaptiveCreatePayload = [ordered]@{
  source_id = $primarySourceId
  question_count = 4
  question_types = @('mcq', 'true_false', 'mcq', 'true_false')
}
$adaptiveSession = Invoke-RestMethod -Method POST -Uri "$base/v1/quiz-sessions" -ContentType 'application/json' -Body ($adaptiveCreatePayload | ConvertTo-Json -Depth 10)
$adaptiveSessionId = "$($adaptiveSession.id)"

$adaptiveFlow = @()
for ($step = 1; $step -le 4; $step++) {
  $next = Invoke-RestMethod -Method GET -Uri "$base/v1/quiz-sessions/$adaptiveSessionId/next-question"
  if ($next.completed -or $null -eq $next.question) {
    break
  }

  $question = $next.question
  $questionType = "$($question.question_type)"
  $shouldBeCorrect = $step -le 2

  $answerBody = $null
  if ($questionType -eq 'true_false') {
    $value = Predict-TrueFalseValue -Explanation "$($question.explanation)" -ShouldBeCorrect $shouldBeCorrect
    $answerBody = @{ answer = @{ value = $value } }
  } elseif ($questionType -eq 'mcq') {
    $choiceId = Predict-McqChoice -Options @($question.options) -Explanation "$($question.explanation)" -ShouldBeCorrect $shouldBeCorrect
    $answerBody = @{ answer = @{ choice_id = "$choiceId" } }
  } elseif ($questionType -eq 'fill_blank') {
    $answerBody = @{ answer = @{ value = 'incorrect-demo-answer' } }
  } else {
    $answerBody = @{ answer = @{ value = 'fallback answer' } }
  }

  $submit = Invoke-RestMethod -Method POST -Uri "$base/v1/quiz-sessions/$adaptiveSessionId/answers/$($question.id)" -ContentType 'application/json' -Body ($answerBody | ConvertTo-Json -Depth 10)

  $adaptiveFlow += [PSCustomObject]@{
    step = $step
    question_id = $question.id
    question_type = $question.question_type
    difficulty_before = $question.difficulty
    submitted_answer = $answerBody.answer
    is_correct = $submit.is_correct
    score = $submit.score
    evaluation_mode = $submit.evaluation_mode
    next_difficulty = $submit.next_difficulty
  }
}

$adaptiveSessionFinal = Invoke-RestMethod -Method GET -Uri "$base/v1/quiz-sessions/$adaptiveSessionId"

$requiredTypes = @('mcq', 'true_false', 'fill_blank')
$requiredTypeExamples = @()
foreach ($questionType in $requiredTypes) {
  $createPayload = @{ source_id = $primarySourceId; question_count = 1; question_types = @($questionType) }
  $session = Invoke-RestMethod -Method POST -Uri "$base/v1/quiz-sessions" -ContentType 'application/json' -Body ($createPayload | ConvertTo-Json -Depth 10)
  $question = Invoke-RestMethod -Method GET -Uri "$base/v1/quiz-sessions/$($session.id)/next-question"

  $requiredTypeExamples += [PSCustomObject]@{
    requested_type = $questionType
    session_id = $session.id
    question = $question.question
  }
}

$apiResponses = [ordered]@{
  health = [ordered]@{
    request = 'GET /health'
    response = $health
  }
  ingestion = [ordered]@{
    request = 'POST /v1/sources (multipart PDF) + GET /v1/sources/{source_id}'
    sources = $ingestedSources
  }
  adaptive_session_create = [ordered]@{
    request = 'POST /v1/quiz-sessions'
    payload = $adaptiveCreatePayload
    response = $adaptiveSession
  }
  adaptive_flow = $adaptiveFlow
  adaptive_session_final = [ordered]@{
    request = "GET /v1/quiz-sessions/$adaptiveSessionId"
    response = $adaptiveSessionFinal
  }
}

$extractedSource = [ordered]@{
  source = $primarySource
  extraction_notes = [ordered]@{
    input_file = $ingestedSources[0].file
    status = $primarySource.status
    chunk_count = $primarySource.chunk_count
    summary_preview = $primarySource.summary
  }
}

$generatedQuizQuestions = [ordered]@{
  source_id = $primarySourceId
  required_types = $requiredTypes
  generated_examples = $requiredTypeExamples
}

$apiResponses | ConvertTo-Json -Depth 25 | Set-Content -Path (Join-Path $repoRoot 'samples/api_responses.json') -Encoding utf8
$extractedSource | ConvertTo-Json -Depth 25 | Set-Content -Path (Join-Path $repoRoot 'samples/extracted_source.json') -Encoding utf8
$generatedQuizQuestions | ConvertTo-Json -Depth 25 | Set-Content -Path (Join-Path $repoRoot 'samples/generated_quiz_question.json') -Encoding utf8

Write-Output "PRIMARY_SOURCE_ID=$primarySourceId"
Write-Output "ADAPTIVE_SESSION_ID=$adaptiveSessionId"
Write-Output 'SAMPLES_REFRESHED=true'
