from app.study.contract import StudySet


class SaveStudySet:
    def __init__(self, validator, sets):
        self._validator, self._sets = validator, sets

    def execute(self, result: StudySet, owner: str) -> dict:
        self._validator.execute(result, owner)
        return self._sets.save_set(result.model_dump(mode="json"), owner)
