# openai_service.py
from openai import OpenAI
import os

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_workout_plan(sex, weight, gymexp, target):
    prompt_text = f"""
    You are a helpful assistant that generates detailed workout plans.
    The user has provided the following details:
    - Sex: {sex}
    - Bodyweight: {weight} kg
    - Gym Experience: {gymexp}

    The user wants a workout focusing on: {target}.

    Please generate a JSON object in the following format:
    {{
      "workout_name": "string",
      "movements": [
        {{
          "name": "string",
          "sets": integer,
          "reps": integer,
          "weight": number,
          "muscle_groups": [
            {{
              "name": "string",
              "impact": integer  // Impact percentage (0-100) indicating how much this movement targets this muscle group
            }}
          ]
        }}
      ]
    }}

    Requirements:
    - Use only the following muscle groups: 
      Chest, Back, Biceps, Triceps, Shoulders, Quadriceps, Hamstrings, Calves, Glutes, Core, Obliques, Lower Back, Forearms, Neck, Hip Flexors.
    - The `workout_name` should summarize the workout focus (e.g., "Leg Day Strength").
    - Each movement should include a name, number of sets, reps per set, and the suggested weight in kg.
    - The `muscle_groups` field should specify which major muscle groups are targeted by the movement, and their relative impact as a percentage (sum of all impacts for a movement must equal 100).
    - The plan should include at least 4-6 movements, focusing on the user's target area and overall balance.

    Example response:
    {{
      "workout_name": "Upper Body Strength",
      "movements": [
        {{
          "name": "Bench Press",
          "sets": 4,
          "reps": 8,
          "weight": 100,
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
          "muscle_groups": [
            {{"name": "Back", "impact": 80}},
            {{"name": "Biceps", "impact": 20}}
          ]
        }}
      ]
    }}

    Please ensure the response is valid JSON and does not include any extraneous text.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt_text}
        ],
        max_tokens=500,
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
    You are a fitness expert. Please provide detailed and clear instructions for the exercise: {movement_name}.
    Include proper form, common mistakes to avoid, suggested resting time and tips for beginners.
    
    Please return only the Title and the instructions for the movement.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful fitness assistant."},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=500,
            temperature=0.7
        )
        instructions = response.choices[0].message.content.strip()
        return instructions
    except Exception as e:
        print(f"Error generating instructions: {e}")
        raise e
