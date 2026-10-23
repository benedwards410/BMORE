"""kce_intake — finds project documents in Outlook and the drop folder, files
them per MTX under the projects root, and runs kce_pipeline when a project's
inputs change. It only ever ADDS copies; it never edits, moves or deletes a
source document, and it never writes to HubSpot, DocuSign or a tracker."""

__version__ = "0.1.0"
