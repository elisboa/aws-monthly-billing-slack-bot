from collections import defaultdict
import boto3
import datetime
import os
import requests
import sys
import calendar

last_month_day = calendar.monthrange(datetime.date.today().year, datetime.date.today().month)[1]

start_date = datetime.date.today().replace(day=1)
end_date = datetime.date.today().replace(day=last_month_day)

# Most X expensive services to list
services_qty = 25
# Acceptable costs (in dollars)
good_cost = 6
# Unacceptable costs (When you should be on red alert)
bad_cost = 10

def report_cost(event, context):
    client = boto3.client('ce')

    query = {
        "TimePeriod": {
            "Start": start_date.strftime('%Y-%m-%d'),
            "End": end_date.strftime('%Y-%m-%d'),
        },
        "Granularity": "MONTHLY",
        "Filter": {
            "Not": {
                "Dimensions": {
                    "Key": "RECORD_TYPE",
                    "Values": [
                        "Credit",
                        "Refund",
                        "Upfront",
                        "Support",
                    ]
                }
            }
        },
        "Metrics": ["UnblendedCost"],
        "GroupBy": [
            {
                "Type": "DIMENSION",
                "Key": "SERVICE",
            },
        ],
    }

    result = client.get_cost_and_usage(**query)

    buffer = "%-40s %5s\n" % ("Services", "Budget")

    cost_by_service = defaultdict(list)

    # Build a map of service -> array of daily costs for the time frame
    for day in result['ResultsByTime']:
        for group in day['Groups']:
            key = group['Keys'][0]
            cost = float(group['Metrics']['UnblendedCost']['Amount'])

            cost_by_service[key].append(cost)

    most_expensive_services = sorted(cost_by_service.items(), key=lambda i: i[1][-1], reverse=True)

    for service_name, costs in most_expensive_services[:services_qty]:
        buffer += "%-40s US$ %5.2f\n" % (service_name, costs[-1])

    other_costs = 0.0
    for service_name, costs in most_expensive_services[services_qty:]:
        for i, cost in enumerate(costs):
            other_costs += cost

    buffer += "%-40s US$ %5.2f\n" % ("Other", other_costs)

    total_costs = 0.0
    for service_name, costs in most_expensive_services:
        for i, cost in enumerate(costs):
            total_costs += cost

    buffer += "%-40s US$ %5.2f\n" % ("Total", total_costs)

    # -- Início do código que não está rodando, ainda não sei por quê
    txt_intro = "Apresentando os %s serviços mais custosos" % (services_qty)
    print(txt_intro)
    # -- Final do código que não está rodando, ainda não sei por quê

    if total_costs < good_cost:
        emoji = ":tada: Billing está abaixo de US$ %5.2f. Parabéns! :confetti_ball:\n" % (good_cost)
    elif total_costs > bad_cost:
        emoji = ":money_with_wings: ATENÇÃO @here o billing está muito alto ─ acima de %5.2f :redsiren: \n" % (bad_cost)
    else:
        emoji = ":zany_face: ATENÇÃO @here o billing está em um nível preocupante ─ acima de US$ %5.2f. O limite é de US$ %5.2f :warning: \n" % (good_cost, bad_cost)

    summary = "%s Billing atual está em: US$ %5.2f" % (emoji, total_costs)

    hook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if hook_url:
        resp = requests.post(
            hook_url,
            json={
                "text": summary + "\n\n```\n" + buffer + "```",
            }
        )

        if resp.status_code != 200:
            print("HTTP %s: %s" % (resp.status_code, resp.text))
    else:
        print(summary)
        print(buffer)
