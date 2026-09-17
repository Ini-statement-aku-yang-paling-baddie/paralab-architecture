"""Runtime guardrails for F5: UI owns identity; model proposes observable fields."""
from copy import deepcopy

REQUIRED_PATCH_KEYS={"measurements","observations"}

def finalize_extraction(selected_trial_id, model_output):
    if not isinstance(selected_trial_id,str) or not selected_trial_id.strip():
        raise ValueError("selected_trial_id must be non-empty")
    if not isinstance(model_output,dict):
        raise ValueError("model_output must be an object")
    patch=model_output.get("proposed_checkpoint_patch")
    if not isinstance(patch,dict) or not REQUIRED_PATCH_KEYS.issubset(patch):
        raise ValueError("model output must include measurement and observation patch")
    if not all(isinstance(patch[k],dict) for k in REQUIRED_PATCH_KEYS):
        raise ValueError("patch groups must be objects")
    result=deepcopy(model_output)
    result["trial_id"]=selected_trial_id
    result["requires_confirmation"]=True
    return result
