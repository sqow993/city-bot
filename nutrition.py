def calc_daily_calories(weight: float, height: float, age: int,
                        gender: str, activity: str) -> float:
    """
    Формула Миффлина — Сан-Жеора.
    gender: 'm' или 'f'
    activity: 'low', 'medium', 'high'
    """
    if gender == "m":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    factors = {"low": 1.2, "medium": 1.55, "high": 1.725}
    return round(bmr * factors.get(activity, 1.2), 1)


# Справочник: средняя калорийность на 100 г
FOOD_DB = {
    "pizza":   {"kcal": 266, "protein": 11.0, "fat": 10.0, "carbs": 33.0},
    "apple":   {"kcal": 52,  "protein": 0.3,  "fat": 0.2,  "carbs": 14.0},
    "banana":  {"kcal": 89,  "protein": 1.1,  "fat": 0.3,  "carbs": 23.0},
    "chicken": {"kcal": 165, "protein": 31.0, "fat": 3.6,  "carbs": 0.0},
    "rice":    {"kcal": 130, "protein": 2.7,  "fat": 0.3,  "carbs": 28.0},
    "burger":  {"kcal": 295, "protein": 17.0, "fat": 14.0, "carbs": 24.0},
    "salad":   {"kcal": 33,  "protein": 1.5,  "fat": 0.2,  "carbs": 6.0},
    "bread":   {"kcal": 265, "protein": 9.0,  "fat": 3.2,  "carbs": 49.0},
    "cheese":  {"kcal": 402, "protein": 25.0, "fat": 33.0, "carbs": 1.3},
    "egg":     {"kcal": 155, "protein": 13.0, "fat": 11.0, "carbs": 1.1},
    "unknown": {"kcal": 150, "protein": 5.0,  "fat": 5.0,  "carbs": 20.0},
}


def calc_nutrition(food: str, weight_grams: float) -> dict:
    """Считает ккал и БЖУ для заданного веса."""
    data = FOOD_DB.get(food, FOOD_DB["unknown"])
    k = weight_grams / 100.0
    return {
        "kcal":    round(data["kcal"]    * k, 1),
        "protein": round(data["protein"] * k, 1),
        "fat":     round(data["fat"]     * k, 1),
        "carbs":   round(data["carbs"]   * k, 1),
    }


def get_recommendation(daily_norm: float, eaten_today: float,
                       meal_nutrition: dict) -> str:
    """
    Формирует текстовую рекомендацию: что убрать / добавить,
    исходя из дневной нормы и текущего приёма пищи.
    """
    after_meal = eaten_today + meal_nutrition["kcal"]
    remaining = daily_norm - after_meal
    lines = []

    # Общая сводка
    lines.append(f"📊 Съедено сегодня: {round(eaten_today, 1)} ккал")
    lines.append(f"🍽 Этот приём: +{meal_nutrition['kcal']} ккал")
    lines.append(f"🔥 Осталось до нормы: {round(remaining, 1)} ккал\n")

    if remaining <= 0:
        lines.append("⚠️ Ты превысил дневную норму. На сегодня лучше остановиться.")
        return "\n".join(lines)

    # Рекомендации по БЖУ
    # Идеальное соотношение: Б ~ 30%, Ж ~ 30%, У ~ 40% от калорий
    total_kcal = after_meal
    if total_kcal > 0:
        p_pct = (meal_nutrition["protein"] * 4 / total_kcal) * 100
        f_pct = (meal_nutrition["fat"]     * 9 / total_kcal) * 100
        c_pct = (meal_nutrition["carbs"]   * 4 / total_kcal) * 100

        lines.append("📈 Соотношение БЖУ в этом блюде:")
        lines.append(f"• Белки: {round(p_pct, 1)}%")
        lines.append(f"• Жиры: {round(f_pct, 1)}%")
        lines.append(f"• Углеводы: {round(c_pct, 1)}%\n")

        # Советы
        tips = []
        if p_pct < 15:
            tips.append("добавь белковый продукт (курицу, творог, яйца)")
        if f_pct > 40:
            tips.append("жиров многовато — в следующий раз меньше масла/соуса")
        if c_pct > 60:
            tips.append("углеводов много — уменьши гарнир или хлеб")

        if tips:
            lines.append("💡 Советы:")
            for t in tips:
                lines.append(f"• {t}")
        else:
            lines.append("✅ Соотношение БЖУ близко к рекомендуемому.")

    return "\n".join(lines)