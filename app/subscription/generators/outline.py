import json

from app.models.subscription_template import SubscriptionFormat
from app.subscription.generators.base import builder_arguments, finish
from app.subscription.outline import OutlineConfiguration
from app.utils.subscription_templates import parse_subscription_document, render_subscription_template


class OutlineSubscriptionGenerator:
    def generate(self, data):
        if not data.profiles:
            return finish("", data, "application/json")
        builder = OutlineConfiguration()
        for profile in data.profiles:
            builder.add(**builder_arguments(profile.connections[0]))
        rendered = render_subscription_template(data.profiles[0].template.content,
                                                {"config": json.loads(builder.render())})
        parse_subscription_document(SubscriptionFormat.outline, rendered)
        return finish(rendered, data, "application/json")
