# openai_service.py
from openai import OpenAI
import os

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_workout_plan(sex, weight, gymexp, target):
    prompt_text = f"""
    You are a helpful assistant that generates workout plans.
    The user is a: {sex}
    User's bodyweight: {weight}
    User's Gym experience: {gymexp}

    The user wants a workout focusing on: {target}.
    Please return a JSON object in this format:
    {{
      "workout_name": "string",
      "movements": [
        {{
          "name": "string",
          "sets": integer,
          "reps": integer,
          "weight": number
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
        max_tokens=300,
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
