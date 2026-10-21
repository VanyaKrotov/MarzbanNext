from app.subscription.generators.base import builder_arguments, finish, map_uri
from app.subscription.v2ray import V2rayShareLink
from app.utils.subscription_templates import parse_subscription_links, render_subscription_template


class UriSubscriptionGenerator:
    def generate(self, data):
        links = []
        for profile in data.profiles:
            connection = profile.connections[0]
            builder = V2rayShareLink()
            builder.add(**builder_arguments(connection, profile.remark))
            mapped = [map_uri(link, connection) for link in builder.links]
            rendered = render_subscription_template(profile.template.content, {
                **connection.context, "links": mapped, "host": connection.template_record(),
            })
            links.extend(parse_subscription_links(rendered))
        if data.external_config:
            links.append(data.external_config)
        if data.reverse:
            links.reverse()
        return finish("\n".join(links), data, "text/plain")
