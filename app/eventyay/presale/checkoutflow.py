from eventyay.presale.checkoutflowstep import (
    AddOnsStep,
    ConfirmStep,
    PaymentStep,
    QuestionsStep,
)
from eventyay.presale.signals import checkout_flow_steps


def get_checkout_flow(event):
    flow = list([step(event) for step in DEFAULT_FLOW])
    for receiver, response in checkout_flow_steps.send(event):
        step = response(event=event)
        if step.priority > 1000:
            raise ValueError('Plugins are not allowed to define a priority greater than 1000')
        flow.append(step)

    # Sort by priority
    flow.sort(key=lambda p: p.priority)

    # Create a double-linked-list for easy forwards/backwards traversal
    last = None
    for step in flow:
        step._previous = last
        if last:
            last._next = step
        last = step
    return flow


DEFAULT_FLOW = (AddOnsStep, QuestionsStep, PaymentStep, ConfirmStep)
