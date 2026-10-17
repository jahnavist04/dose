# Safety notes

Dose is a reminder and safety-net tool. It is not medical advice and does not replace a doctor or pharmacist.

- Prescription photos are read by an AI model, so results are shown to the user for confirmation before they are saved
- The model is told to write "unclear" instead of guessing, and never to add medicines that are not written
- Interaction warnings come only from named sources listed in data/interactions.json, never from the model's guess
- Serious warnings always say "ask your pharmacist"
- Demo and test data are fake. No real patient data is stored in this repo
