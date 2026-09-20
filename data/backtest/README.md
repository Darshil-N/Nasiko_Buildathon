# Back-test Data Format

Back-test cases are JSON files named by category, e.g. `cafe_cases.json`.

Format:
```json
[
  {
    "city": "Pune",
    "tier": "premium",
    "expected_top_3_zones": [
      "Koregaon Park",
      "Kalyani Nagar",
      "Viman Nagar"
    ],
    "expected_bottom_zones": [
      "Katraj"
    ]
  }
]
```
