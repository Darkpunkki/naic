import json

from openai import OpenAI
import os

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_workout_plan(sex, weight, gymexp, target, goal="general_fitness", restrictions=""):
    # Build restriction text if provided
    restriction_text = ""
    if restrictions and restrictions.strip():
        restriction_text = f"""
    IMPORTANT - User Restrictions:
    The user has specified the following restrictions or limitations: {restrictions}
    You MUST avoid any movements that conflict with these restrictions. Do not include exercises that target restricted muscle groups or could aggravate mentioned injuries."""

    # Map goal to workout style guidance
    goal_guidance = {
        "muscle_growth": "Focus on hypertrophy: moderate weight, 8-12 reps, controlled tempo, adequate volume per muscle group.",
        "strength": "Focus on strength: heavier weights, lower reps (3-6), compound movements, longer rest periods.",
        "cardio": "Focus on cardio/endurance: lighter weights, higher reps (15-20+), shorter rest periods, circuit-style if appropriate.",
        "weight_loss": "Focus on fat burning: moderate weights, higher reps (12-15), supersets, minimal rest to keep heart rate elevated.",
        "general_fitness": "Focus on balanced fitness: mix of compound and isolation exercises, moderate reps (8-12), well-rounded approach."
    }.get(goal, "Focus on balanced fitness: mix of compound and isolation exercises, moderate reps (8-12), well-rounded approach.")

    prompt_text = f"""
    You are a helpful assistant that generates detailed workout plans.
    The user has provided the following details:
    - Sex: {sex}
    - Bodyweight: {weight} kg
    - Gym Experience: {gymexp}
    - Workout Goal: {goal}

    Goal Guidance: {goal_guidance}

    The user wants a workout focusing on: {target}.
    {restriction_text}

    Please generate a JSON object in the following format:
    {{
      "workout_name": "string",
      "movements": [
        {{
          "name": "string",
          "sets": integer,
          "reps": integer,
          "weight": number,
          "is_bodyweight": boolean,  // If this exercise is typically done with bodyweight, set to true
          "muscle_groups": [
            {{
              "name": "string",
              "impact": integer  // Impact percentage (0-100)
            }}
          ]
        }}
      ]
    }}

    Requirements:
    - Use only the following muscle groups: 
      Chest, Back, Biceps, Triceps, Shoulders, Quadriceps, Hamstrings, Calves, Glutes, Core,
      Obliques, Lower Back, Forearms, Neck, Hip Flexors, Adductors, Abductors.
    - The `workout_name` should summarize the workout focus (e.g., "Leg Day Strength").
    - Each movement should include a name, number of sets, reps per set, and the suggested weight in kg.
    - If the exercise is typically done with bodyweight (like push-ups, dips, pull-ups), set "weight": 0 and "is_bodyweight": true.
      Otherwise, if there's an external load, set "is_bodyweight": false.
    - The `muscle_groups` field must sum to 100% for each movement.
    - The plan should include at least 4-6 movements, focusing on the user's target area and overall balance.
    - Ensure the response is valid JSON and does not include any extraneous text.

    Example response:
    {{
      "workout_name": "Upper Body Strength",
      "movements": [
        {{
          "name": "Bench Press",
          "sets": 4,
          "reps": 8,
          "weight": 100,
          "is_bodyweight": false,
          "muscle_groups": [
            {{"name": "Chest", "impact": 70}},
            {{"name": "Triceps", "impact": 30}}
          ]
        }},
        {{
          "name": "Pull-Ups",
          "sets": 3,
          "reps": 12,
          "weight": 0,
          "is_bodyweight": true,
          "muscle_groups": [
            {{"name": "Back", "impact": 80}},
            {{"name": "Biceps", "impact": 20}}
          ]
        }}
      ]
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt_text}
        ],
        max_tokens=700,
        temperature=0.7
    )

    return response.choices[0].message.content.strip()




def generate_movement_instructions(movement_name):
    """
    Generates detailed instructions for performing a specific movement.
    :param movement_name: Name of the movement to fetch instructions for.
    :return: Detailed instructions as a string.
    """
    prompt_text = f"""
    You are a fitness expert. Provide instructions for the exercise: {movement_name}.

    Use EXACTLY this format with these section headers (use the emojis as shown):

    🎯 Setup
    • [1-2 bullet points on starting position]

    💪 Execution
    • [2-3 bullet points on how to perform the movement]

    ⚠️ Common Mistakes
    • [2-3 bullet points on what to avoid]

    💡 Tips
    • [1-2 quick tips for beginners]

    ⏱️ Rest: [recommended rest time between sets]

    Rules:
    - Use bullet points (•) for each item
    - Keep each bullet point to one short sentence
    - Do NOT use markdown formatting (no **, no #, no bold)
    - Do NOT include the exercise name as a title
    - Keep it concise for mobile viewing
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful fitness assistant."},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=300,
            temperature=0.7
        )
        instructions = response.choices[0].message.content.strip()
        return instructions
    except Exception as e:
        print(f"Error generating instructions: {e}")
        raise e


def generate_movement_info(movement_name):
    """
    Calls ChatGPT to get the muscle groups for the given movement_name,
    plus whether it's bodyweight or not.
    Returns a dict like:
    {
      "movement_name": "Dragon Flags",
      "is_bodyweight": true,
      "weight": 0,
      "muscle_groups": [
        {"name": "Core", "impact": 50},
        {"name": "Hip Flexors", "impact": 50}
      ]
    }
    """
    prompt_text = f"""
    You are a helpful assistant that knows about fitness exercises. 
    The user wants to add a new movement called '{movement_name}' to their workout plan.
    Please respond with JSON in the format:
    {{
      "movement_name": "string",
      "is_bodyweight": boolean,
      "weight": number, // if bodyweight is true, set this to 0
      "muscle_groups": [
        {{
          "name": "string",
          "impact": integer // sum of all impacts must be 100
        }}
      ]
    }}

    Requirements:
    - Use only these muscle groups:
      Chest, Back, Biceps, Triceps, Shoulders, Quadriceps, Hamstrings, Calves, Glutes, Core,
      Obliques, Lower Back, Forearms, Neck, Hip Flexors, Adductors, Abductors.
    - If the movement is typically done as bodyweight (e.g., push-ups, pull-ups, dips), set "is_bodyweight": true and "weight": 0.
    - If there's typically an external load, set "is_bodyweight": false, and provide a recommended weight in kg (like 10, 20, etc.).
    - The sum of 'impact' across all muscle groups should be 100.
    - No extra text, only valid JSON.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt_text}
        ],
        max_tokens=300,
        temperature=0.7
    )

    raw_content = response.choices[0].message.content.strip()
    try:
        movement_json = json.loads(raw_content)
        return movement_json
    except json.JSONDecodeError:
        # Fallback if something unexpected
        return {
            "movement_name": movement_name,
            "is_bodyweight": False,
            "weight": 0,
            "muscle_groups": []
        }

def generate_weekly_workout_plan(sex, weight, gymexp, target, gym_days, session_duration, goal="general_fitness", restrictions=""):
    # Build restriction text if provided
    restriction_text = ""
    if restrictions and restrictions.strip():
        restriction_text = f"""
    IMPORTANT - User Restrictions:
    The user has specified the following restrictions or limitations: {restrictions}
    You MUST avoid any movements that conflict with these restrictions throughout the entire weekly plan. Do not include exercises that target restricted muscle groups or could aggravate mentioned injuries."""

    # Map goal to workout style guidance
    goal_guidance = {
        "muscle_growth": "Focus on hypertrophy: moderate weight, 8-12 reps, controlled tempo, adequate volume per muscle group. Structure the week to hit each major muscle group with sufficient volume.",
        "strength": "Focus on strength: heavier weights, lower reps (3-6), compound movements, longer rest periods. Prioritize progressive overload across the week.",
        "cardio": "Focus on cardio/endurance: lighter weights, higher reps (15-20+), shorter rest periods, circuit-style workouts. Include variety to maintain cardiovascular challenge.",
        "weight_loss": "Focus on fat burning: moderate weights, higher reps (12-15), supersets, minimal rest to keep heart rate elevated. Full-body sessions work well.",
        "general_fitness": "Focus on balanced fitness: mix of compound and isolation exercises, moderate reps (8-12), well-rounded approach hitting all muscle groups across the week."
    }.get(goal, "Focus on balanced fitness: mix of compound and isolation exercises, moderate reps (8-12), well-rounded approach hitting all muscle groups across the week.")

    prompt_text = f"""
    You are a helpful assistant that generates detailed weekly workout plans.
    The user has provided the following details:
    - Sex: {sex}
    - Bodyweight: {weight} kg
    - Gym Experience: {gymexp}
    - Workout Focus: {target}
    - Workout Goal: {goal}
    - They plan to work out {gym_days} times per week, with each session lasting approximately {session_duration} minutes.

    Goal Guidance: {goal_guidance}
    {restriction_text}

    Please generate a JSON object with a key "weekly_plan" that is an array of workout objects.
    Each workout object should have:
      - "day": a label such as "Day 1", "Day 2", etc.
      - "workout_name": a string summarizing the focus for that day (e.g. "Upper Body Strength")
      - "movements": an array of movement objects.
    Each movement object should follow this format:
    {{
      "name": "string",
      "sets": integer,
      "reps": integer,
      "weight": number,
      "is_bodyweight": boolean,
      "muscle_groups": [
        {{
          "name": "string",
          "impact": integer
        }}
      ]
    }}

    Requirements:
    - Include at least 4-6 movements for each workout.
    - The muscle group impacts in each movement should sum to 100.
    - Ensure the JSON is valid and contains no extra text.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt_text}
        ],
        # WIP: 1000 tokens was too low, 2000 will also be too low if user want eg. 7 days a week
        max_tokens=2000,
        temperature=0.7
    )
    
    return response.choices[0].message.content.strip()
