from csai_langchain_modify.routing.router import Router
from csai_langchain_modify.service.csai_service import CSAIService


router = Router()
service = CSAIService()


questions = [

    "Who are the directors of Action Multiple?",

    "List shareholders of Action Multiple",

    "Beneficial owners of Action Multiple",

    "Which companies is KHOR PENG CHAI appointed as director?",

    "How to transfer shares?"

]


for question in questions:

    print("=" * 80)

    print(question)

    intent = router.detect(question)

    print(intent)

    result = service.execute(intent)

    print(result)

print("=" * 80)