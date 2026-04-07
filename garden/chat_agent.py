"""
AI Garden Chat Agent.
Uses the Anthropic API with tool use to answer gardening questions
grounded in real plant/zone data and take actions like adding plants to the garden.
"""
import json
import logging
from anthropic import Anthropic
from django.conf import settings
from .models import FrostDateByZone, Plant, CompanionRelationship
from .services import lookup_zone
from django.db.models import Q

logger = logging.getLogger(__name__)

# --- Tool Definitions ---
# These tell Claude what functions it can call. Claude reads these descriptions
# to decide which tool to use for a given question.

TOOLS = [
    {
        "name": "lookup_zone",
        "description": "Look up the USDA hardiness zone and frost dates for a zip code. Use this when the user mentions a zip code or location and you need to find their growing zone, frost dates, or growing season length.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zip_code": {
                    "type": "string",
                    "description": "5-digit US zip code"
                }
            },
            "required": ["zip_code"]
        }
    },
    {
        "name": "search_plants",
        "description": "Search for plants in the database by name or keyword. Use this when the user asks about a specific plant, vegetable, herb, or flower, or wants to know what plants are available. Returns matching plants with their growing details.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term — plant name, variety, or type (e.g. 'tomato', 'basil', 'herb')"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_planting_calendar",
        "description": "Get personalized planting dates for a specific plant in a specific hardiness zone. Returns when to start indoors, transplant, direct sow, and expected harvest window. Use this when the user asks WHEN to plant something.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plant_id": {
                    "type": "integer",
                    "description": "The plant ID from a previous search_plants result"
                },
                "zone": {
                    "type": "string",
                    "description": "USDA hardiness zone, e.g. '6b', '7a'"
                }
            },
            "required": ["plant_id", "zone"]
        }
    },
    {
        "name": "get_companions",
        "description": "Get companion planting information for a specific plant — which plants grow well together and which should be kept apart. Use this when the user asks about companion planting, what to plant next to something, or what to avoid planting together.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plant_id": {
                    "type": "integer",
                    "description": "The plant ID from a previous search_plants result"
                }
            },
            "required": ["plant_id"]
        }
    },
    {
        "name": "add_to_garden",
        "description": "Add a plant to the user's garden. Use this when the user says they want to grow something, asks you to add a plant to their garden, or says something like 'let's grow tomatoes'. Returns the plant info so you can confirm what was added.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plant_id": {
                    "type": "integer",
                    "description": "The plant ID to add"
                }
            },
            "required": ["plant_id"]
        }
    },
    {
        "name": "remove_from_garden",
        "description": "Remove a plant from the user's garden. Use this when the user says they want to remove a plant or don't want to grow something anymore.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plant_id": {
                    "type": "integer",
                    "description": "The plant ID to remove"
                }
            },
            "required": ["plant_id"]
        }
    },
    {
        "name": "list_garden",
        "description": "List all plants currently in the user's garden with their planting calendars. Use this when the user asks what's in their garden, wants to see their full calendar, or asks about their garden plan.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
]


def build_system_prompt(zip_code=None, zone_str=None):
    #Build the system prompt with user context.
    base = """You are a knowledgeable, friendly gardening assistant. You help people plan their vegetable and herb gardens with accurate, practical advice.

You have access to a database of plants with detailed growing information sourced from Rutgers Cooperative Extension and other university agricultural sources. You also have tools to look up USDA hardiness zones, get personalized planting calendars, check companion planting relationships, and manage the user's garden.

IMPORTANT GUIDELINES:
- Always use your tools to look up real data rather than guessing. If someone asks about a plant, search for it first.
- When giving planting dates, always use the get_planting_calendar tool with the user's actual zone — never make up dates.
- If you don't have a plant in the database, say so honestly and give general advice.
- Be conversational and practical. These are home gardeners, not farmers.
- When you add a plant to the garden, confirm what you added and mention any relevant companion planting info.
- Keep responses concise but helpful. Don't dump every detail unless asked."""

    if zip_code and zone_str:
        base += f"""

USER CONTEXT:
- Zip code: {zip_code}
- USDA Hardiness Zone: {zone_str}
Use this zone for all planting calendar lookups unless the user specifies a different location."""

    return base


# --- Tool Execution ---

def execute_tool(tool_name, tool_input, garden_state):
    # Execute a tool call and return the result.
    # garden_state is a dict with 'plants' (list of {id, name}) and 'zip_code'.
    # Returns (result_text, updated_garden_state).
    try:
        if tool_name == "lookup_zone":
            return _tool_lookup_zone(tool_input)

        elif tool_name == "search_plants":
            return _tool_search_plants(tool_input)

        elif tool_name == "get_planting_calendar":
            return _tool_get_calendar(tool_input)

        elif tool_name == "get_companions":
            return _tool_get_companions(tool_input)

        elif tool_name == "add_to_garden":
            return _tool_add_to_garden(tool_input, garden_state)

        elif tool_name == "remove_from_garden":
            return _tool_remove_from_garden(tool_input, garden_state)

        elif tool_name == "list_garden":
            return _tool_list_garden(garden_state)

        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        logger.exception(f"Tool execution error: {tool_name}")
        return json.dumps({"error": str(e)})


def _tool_lookup_zone(tool_input):
    zip_code = tool_input.get("zip_code", "")
    frost_data, zone_str, error = lookup_zone(zip_code)

    if frost_data:
        return json.dumps({
            "zip_code": zip_code,
            "zone": zone_str,
            "last_frost": frost_data.last_frost_for_year().strftime("%B %d"),
            "first_frost": frost_data.first_frost_for_year().strftime("%B %d"),
            "growing_season_days": frost_data.growing_season_days,
        })
    elif zone_str:
        return json.dumps({"zip_code": zip_code, "zone": zone_str, "warning": error})
    else:
        return json.dumps({"error": error or "Zip code not found."})


def _tool_search_plants(tool_input):
    query = tool_input.get("query", "")
    plants = Plant.objects.filter(
        Q(name__icontains=query) | Q(variety__icontains=query) | Q(plant_type__icontains=query)
    )[:10]

    results = []
    for p in plants:
        results.append({
            "id": p.pk,
            "name": p.display_name,
            "type": p.plant_type,
            "days_to_maturity": f"{p.days_to_maturity_min}-{p.days_to_maturity_max}",
            "sun": p.get_sun_requirement_display(),
            "water": p.get_water_needs_display(),
            "spacing_inches": p.spacing_inches,
            "start_indoors": p.start_indoors,
            "can_direct_sow": p.can_direct_sow,
            "description": p.description,
        })
    return json.dumps({"results": results, "count": len(results)})


def _tool_get_calendar(tool_input):
    plant_id = tool_input.get("plant_id")
    zone_str = tool_input.get("zone", "")

    try:
        plant = Plant.objects.get(pk=plant_id)
    except Plant.DoesNotExist:
        return json.dumps({"error": f"Plant with ID {plant_id} not found."})

    frost_data = FrostDateByZone.objects.filter(zone=zone_str).first()
    if not frost_data:
        # Fallback to base zone
        base = zone_str[:-1] if len(zone_str) >= 2 else zone_str
        frost_data = FrostDateByZone.objects.filter(zone__startswith=base).first()
    if not frost_data:
        return json.dumps({"error": f"No frost data for zone {zone_str}."})

    cal = plant.get_calendar(frost_data)
    result = {
        "plant": plant.display_name,
        "zone": cal["zone"],
        "last_frost": cal["last_frost"].strftime("%B %d"),
        "first_frost": cal["first_frost"].strftime("%B %d"),
    }
    for key in ["start_indoors", "transplant", "direct_sow", "harvest_start", "harvest_end"]:
        if key in cal:
            result[key] = cal[key].strftime("%B %d")
    if cal.get("frost_warning"):
        result["frost_warning"] = "Harvest may extend past first frost. Consider frost protection."

    return json.dumps(result)


def _tool_get_companions(tool_input):
    plant_id = tool_input.get("plant_id")

    try:
        plant = Plant.objects.get(pk=plant_id)
    except Plant.DoesNotExist:
        return json.dumps({"error": f"Plant with ID {plant_id} not found."})

    rels = CompanionRelationship.objects.filter(
        Q(plant_a=plant) | Q(plant_b=plant)
    ).select_related("plant_a", "plant_b")

    companions = []
    antagonists = []
    for rel in rels:
        other = rel.plant_b if rel.plant_a == plant else rel.plant_a
        entry = {"name": other.display_name, "id": other.pk, "reason": rel.reason}
        if rel.relationship == "companion":
            companions.append(entry)
        else:
            antagonists.append(entry)

    return json.dumps({
        "plant": plant.display_name,
        "good_companions": companions,
        "antagonists": antagonists,
    })


def _tool_add_to_garden(tool_input, garden_state):
    plant_id = tool_input.get("plant_id")
    try:
        plant = Plant.objects.get(pk=plant_id)
    except Plant.DoesNotExist:
        return json.dumps({"error": f"Plant with ID {plant_id} not found."})

    plants = garden_state.get("plants", [])
    if any(p["id"] == plant_id for p in plants):
        return json.dumps({"status": "already_in_garden", "plant": plant.display_name})

    plants.append({"id": plant.pk, "name": plant.display_name})
    garden_state["plants"] = plants

    return json.dumps({
        "status": "added",
        "plant": plant.display_name,
        "plant_id": plant.pk,
        "garden_count": len(plants),
    })


def _tool_remove_from_garden(tool_input, garden_state):
    plant_id = tool_input.get("plant_id")
    plants = garden_state.get("plants", [])
    removed_name = None

    for p in plants:
        if p["id"] == plant_id:
            removed_name = p["name"]
            break

    if not removed_name:
        return json.dumps({"status": "not_in_garden", "plant_id": plant_id})

    garden_state["plants"] = [p for p in plants if p["id"] != plant_id]

    return json.dumps({
        "status": "removed",
        "plant": removed_name,
        "garden_count": len(garden_state["plants"]),
    })


def _tool_list_garden(garden_state):
    plants = garden_state.get("plants", [])
    zip_code = garden_state.get("zip_code", "")

    if not plants:
        return json.dumps({"status": "empty", "message": "The garden is empty. Help the user add some plants!"})

    result = {"plants": [], "zip_code": zip_code}

    # If we have a zip, include calendar info
    zone_str = None
    frost_data = None
    if zip_code:
        frost_data_obj, zone_str, _ = lookup_zone(zip_code)
        frost_data = frost_data_obj

    for p_info in plants:
        try:
            plant = Plant.objects.get(pk=p_info["id"])
            entry = {"id": plant.pk, "name": plant.display_name, "type": plant.plant_type}
            if frost_data:
                cal = plant.get_calendar(frost_data)
                for key in ["start_indoors", "transplant", "direct_sow", "harvest_start", "harvest_end"]:
                    if key in cal:
                        entry[key] = cal[key].strftime("%B %d")
            result["plants"].append(entry)
        except Plant.DoesNotExist:
            continue

    return json.dumps(result)


# --- Main Chat Function ---

def chat(messages, garden_state):
    """
    Send messages to Claude with tools, handle the tool use loop,
    and return the final response + any garden state changes.

    Args:
        messages: list of {"role": "user"|"assistant", "content": "..."}
        garden_state: dict with "plants" list and "zip_code"

    Returns:
        (response_text, garden_state, garden_actions)
        garden_actions is a list of {"action": "add"|"remove", "plant_id": int, "plant_name": str}
    """
    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    garden_actions = []

    system_prompt = build_system_prompt(
        zip_code=garden_state.get("zip_code"),
        zone_str=garden_state.get("zone_str"),
    )

    # Agent loop — Claude may call tools multiple times before giving a final answer
    current_messages = list(messages)
    max_iterations = 10  # safety limit

    for _ in range(max_iterations):
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=current_messages,
        )

        # Check if Claude wants to use tools
        if response.stop_reason == "tool_use":
            # Claude's response may contain text + tool calls
            assistant_content = response.content

            # Process each tool call
            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    logger.info(f"Tool call: {tool_name}({json.dumps(tool_input)})")

                    # Execute the tool
                    result = execute_tool(tool_name, tool_input, garden_state)

                    # Track garden actions for the frontend
                    if tool_name == "add_to_garden":
                        result_data = json.loads(result)
                        if result_data.get("status") == "added":
                            garden_actions.append({
                                "action": "add",
                                "plant_id": result_data["plant_id"],
                                "plant_name": result_data["plant"],
                            })
                    elif tool_name == "remove_from_garden":
                        result_data = json.loads(result)
                        if result_data.get("status") == "removed":
                            garden_actions.append({
                                "action": "remove",
                                "plant_id": tool_input["plant_id"],
                                "plant_name": result_data["plant"],
                            })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Add assistant's response and tool results to messages, then loop
            current_messages.append({"role": "assistant", "content": assistant_content})
            current_messages.append({"role": "user", "content": tool_results})

        else:
            # Claude gave a final text response — we're done
            text_parts = [block.text for block in response.content if hasattr(block, "text")]
            final_text = "\n".join(text_parts)
            return final_text, garden_state, garden_actions

    # Safety fallback if we hit max iterations
    return "I got a bit lost there — could you try rephrasing your question?", garden_state, garden_actions
