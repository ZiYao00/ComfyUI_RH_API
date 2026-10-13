"""
RH_BatchExecute Node - Execute a batch of tasks on RunningHub
"""

from .rh_utils import _validate_config
from .rh_client import RHClient, RHTaskSubmissionUncertainError
from .rh_task_journal import record_created_task

class RH_BatchExecute:
    """
    A node to execute a batch of tasks on RunningHub using a parameter bundle.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("RH_CONFIG", ),
                "workflow_id": ("STRING", {"multiline": False, "default": ""}),
                "param_bundle": ("RH_PARAM_BUNDLE", ),
            },
            "optional": {
                "instance_type": (["auto", "default", "plus", "ultra"], {
                    "default": "auto",
                    "tooltip": "Auto omits instanceType; Default=24GB, Plus=48GB, Ultra=84GB.",
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("task_ids",)
    FUNCTION = "batch_execute"
    CATEGORY = "Ken-Chen/RH-API"

    def batch_execute(self, config, workflow_id, param_bundle, instance_type="auto"):
        """
        Executes a task for each parameter set in the bundle.
        """
        _validate_config(config)
        client = RHClient(config["api_key"], config["base_url"])

        selected_instance = RHClient.resolve_instance_type(instance_type)

        if not workflow_id:
            raise ValueError("Workflow ID is required.")
        if not isinstance(param_bundle, list) or not param_bundle:
            raise ValueError("Parameter bundle is invalid or empty.")

        print(f"🚀 Starting Batch Execution for {len(param_bundle)} tasks...")
        task_ids = []
        journal_config = {**config, "workflow_or_app_id": str(workflow_id), "is_ai_app": False}

        for i, params_list in enumerate(param_bundle):
            print(f"  - Submitting task {i+1}/{len(param_bundle)}...")
            try:
                task_id = client.create_task(
                    workflow_or_app_id=workflow_id,
                    params=params_list,
                    is_ai_app=False,
                    use_high_performance=False,
                    instance_type=selected_instance,
                    on_task_created=lambda confirmed_id: record_created_task(
                        confirmed_id, journal_config, instance_type=selected_instance, origin="batch"
                    ),
                )
                task_ids.append(task_id)
                print(f"    ✓ Task submitted successfully. Task ID: {task_id}")
            except RHTaskSubmissionUncertainError:
                # Stop immediately: continuing a paid batch after an ambiguous
                # submission makes duplicate-task reconciliation unsafe.
                print(f"    Warning: task {i+1} submission uncertain. Previous confirmed IDs: {','.join(task_ids) or '(none)'}.")
                raise
            except Exception:
                # A definite error ends the batch; later submissions can
                # otherwise incur new charges without operator consent.
                confirmed = ",".join(task_ids) or "(none)"
                raise RuntimeError(
                    f"RH Batch stopped at item {i+1}/{len(param_bundle)}. "
                    f"Previously confirmed task IDs: {confirmed}. "
                    "No further tasks were submitted. Recover from the RH task journal."
                ) from None

        if not task_ids:
            raise Exception("All task submissions failed for the batch.")

        # Return a comma-separated string of task IDs
        task_id_string = ",".join(task_ids)
        print(f"✅ Batch submission complete. Task IDs: {task_id_string}")
        
        return (task_id_string,)

