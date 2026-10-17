# Amazon Bedrock usage in Dose

## What we use it for
- Reading prescription photos and extracting medicine name, strength, frequency pattern (like 1-0-1) and duration
- (Planned) Writing the weekly family adherence summary

## Model and region
- Model: Amazon Nova Lite 1.0, on-demand
- Region: ap-southeast-2

## Test results so far
- 2026-10-17: a handwritten sample prescription (tests/samples/rx_handwritten_01.jpg) was read correctly in the Bedrock playground: 3 of 3 medicines, strengths and patterns. Latency about 700 ms.

## Safety choices
- The prompt tells the model to write "unclear" instead of guessing and never to add medicines that are not written
- Extraction results are shown to the user for confirmation before they are saved
- Dose is a reminder tool, not medical advice

## Known limits
- Tested only on clear handwriting so far
- Messy handwriting and 5mg vs 50mg cases still to test
