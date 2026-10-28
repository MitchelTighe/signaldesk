# Nebius and NVIDIA technology feedback

This feedback is based on the recorded evaluations and their documentation, not new vendor calls.

## Nebius Token Factory

The OpenAI-compatible chat completions endpoint supported recorded calls to both Nemotron models with JSON-object responses and returned token usage for cost estimates. In the second-author run, nine completed drafts were rejected even though they had `finish_reason=stop`; the retained records cannot identify whether schema, citation or step checks failed. SignalDesk treated rejected drafts as handoffs and added fixed local rejection codes for future runs without retaining raw draft text. Please provide clearer structured response diagnostics for incomplete or unusable JSON output, including the distinction between completion and usable structured content. The historical rejection causes remain unknown. [Evidence](docs/RUNTIME-EVIDENCE.md#second-author-check-ten-new-incidents-october-22) · [diagnostics](docs/FINAL-VALIDATION.md).

## NVIDIA Nemotron 3.5 Lightning

Lightning provided the first draft in the cost-aware route. With reasoning enabled and a 1,600-token output cap, an earlier run exhausted the budget and returned empty content with `finish_reason=length`. The recorded route sends `chat_template_kwargs: {"enable_thinking": false}` for Lightning. Please make reasoning token consumption and the remaining answer budget easier to understand and control so a structured answer can be returned within a configured cap. [Evidence](docs/RUNTIME-EVIDENCE.md).

## NVIDIA Nemotron 3 Super

With reasoning enabled, Super caught the stop caveats in X02 and X03 that the reasoning-off exploratory runs missed. With reasoning off, it proposed cleaning despite the ticket context in those cases. SignalDesk uses Super with reasoning on as a second reader before physical actions and after vetoes or abstentions, with independent validation and a human decision. Please improve adherence to explicit stop caveats in structured incident-triage responses, including when reasoning is disabled. [Evidence](docs/RUNTIME-EVIDENCE.md).
