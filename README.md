# Speckled 

Experiment to validate whether https://github.com/reworkd/tarsier + gpt-4o can drive playwright tests.

Findings:

* Text/OCR doesn't seem to work as well as image.
* It didn't tag the checkbox (so you can't complete TODOs)
* It didn't automatically figure out that you needed to hit enter to submit a TODO.

Otherwise it worked very well, no issues with xpath selectors and the LLM seemed to understand the page content well.
