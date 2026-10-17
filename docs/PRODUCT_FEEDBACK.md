# Product feedback: Amazon Bedrock

## What we used it for
Reading handwritten prescription photos and extracting medicine name, strength, frequency pattern (like 1-0-1) and duration, using Amazon Nova Lite 1.0 (on-demand, ap-southeast-2).

## What worked well
- The playground made it easy to test an image plus a prompt with no code
- Nova Lite read a handwritten sample correctly (3 of 3 medicines, strengths and patterns) in about 700 ms
- It followed the instruction to not add medicines that were not written

## What needs work
- A new account hit AccessDeniedException ("account is currently being verified") on the first call, and nothing in the console showed the verification status
- The model picker lists many models, and it was hard to tell which ones are best for reading handwriting

## Onboarding
Creating the account, setting a budget, and finding the playground took about an hour. The verification wait was the main delay.

## Would we build with it again?
Yes. The speed and low cost suit a reminder app like Dose.
