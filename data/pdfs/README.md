# Peblo PDF Sources

Place the evaluator PDFs in this directory before running the ingestion pipeline.

## Required Files

| File | Grade | Subject |
|------|-------|---------|
| `peblo_pdf_grade1_math_numbers.pdf` | Grade 1 | Mathematics |
| `peblo_pdf_grade3_science_plants_animals.pdf` | Grade 3 | Science |
| `peblo_pdf_grade4_english_grammar.pdf` | Grade 4 | English |

## Upload via API

Once the server is running, ingest each PDF with:

```bash
curl -X POST http://127.0.0.1:8000/v1/sources \
  -F "title=Grade 1 Math" \
  -F "file=@data/pdfs/peblo_pdf_grade1_math_numbers.pdf;type=application/pdf"
```

Then poll `GET /v1/sources/{source_id}` until `status` is `ready`.
