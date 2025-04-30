from services.RecommendationService import RecommendationService
from fastapi import Depends

# Создаём единственный экземпляр сервиса при старте приложения
recommendation_service = RecommendationService()

def get_recommendation_service():

    return recommendation_service