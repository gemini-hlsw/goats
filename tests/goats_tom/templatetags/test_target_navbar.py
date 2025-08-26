from django.template import Context, Template


# Test function
def test_render_target_navbar():
    # Create a RequestContext-like object
    context = Context({"target": {"name": "test", "id": 1}})

    # Define a simple template that uses the custom tag
    template_to_render = Template(
        "{% load target_navbar %}"  # Ensure you load your custom template tag library
        "{% render_target_navbar %}"
    )

    # Render the template with context
    rendered_template = template_to_render.render(context)

    # Assertions to check if the context passed contains what we expect
    assert "Navigation tabs" in rendered_template
