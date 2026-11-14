"""Short-lived, unanimous party consent before creating any training clones."""
import asyncio
import logging
import secrets
import time

from protocol import Str
from training import party

log = logging.getLogger(__name__)
TIMEOUT = 60


class Request:
    def __init__(self, owner, params, members, check_entry, enter):
        self.owner, self.params = owner, dict(params)
        self.members = tuple(members)
        self.group, self.room = owner.party(), owner.room
        self.token = secrets.token_hex(16)
        self.accepted = {owner}
        self.deadline = time.monotonic() + TIMEOUT
        self.timer = None
        self.check_entry, self.enter = check_entry, enter

    def finish(self, message=''):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None
        targets = [member for member in self.members
                   if getattr(member, 'training_entry', None) is self]
        for member in targets:
            member.training_entry = None
        for member in targets:
            if not member.closed:
                try:
                    member.send('tg', op='entry_end', confirmation=Str(self.token))
                    if message:
                        member.answer(message)
                except Exception:
                    log.exception('Could not close training invitation for %s', member.char_id)

    def expire(self):
        self.finish('Вход на полигон отменён: не все участники ответили за 60 секунд.')

    def validate(self):
        if (any(member.closed or member.room is not self.room
                or member.party() is not self.group
                or getattr(member, 'training_entry', None) is not self
                for member in self.members)
                or self.group.leader != self.owner.char_id):
            raise ValueError('Вход на полигон отменён: состав или положение отряда изменились.')
        self.check_entry(self.owner, self.params)
        if set(party.entrants(self.owner)) != set(self.members):
            raise ValueError('Вход на полигон отменён: состав участников изменился.')

    def reply(self, member, params):
        if (member is self.owner or member not in self.members
                or params.get('confirmation') != self.token
                or params.get('accept') not in (0, 1)):
            return
        if time.monotonic() >= self.deadline:
            self.expire()
            return
        if member in self.accepted:
            return
        if params['accept'] == 0:
            self.finish('Вход на полигон отменён: участник отряда отказался.')
            return
        try:
            self.validate()
        except ValueError as exc:
            self.finish(str(exc))
            return
        self.accepted.add(member)
        if len(self.accepted) != len(self.members):
            member.answer('Согласие принято. Ожидаем остальных участников отряда.')
            return
        # Consume consent before entry: duplicate/late replies cannot re-enter.
        self.finish()
        try:
            self.enter(self.owner, self.params)
        except Exception:
            log.exception('Could not enter range after party consent')
            for participant in self.members:
                if not participant.closed:
                    participant.answer('Не удалось открыть полигон. Повторите задание у Берта.')


def request(owner, params, check_entry, enter):
    check_entry(owner, params)
    members = party.entrants(owner)
    if any(getattr(member, 'training_entry', None) is not None for member in members):
        raise ValueError('Отряд уже ожидает подтверждения входа на полигон.')
    if len(members) == 1:
        enter(owner, params)
        return
    if any(not getattr(member, 'training_entry_confirmation', False) for member in members[1:]):
        raise ValueError('Для подтверждения входа участникам отряда нужно обновить клиент.')
    pending = Request(owner, params, members, check_entry, enter)
    pending.timer = asyncio.get_running_loop().call_later(TIMEOUT, pending.expire)
    for member in members:
        member.training_entry = pending
    try:
        for member in members[1:]:
            member.send('tg', op='entry_invite', confirmation=Str(pending.token),
                        leader=Str(owner.nick), seconds=TIMEOUT)
        owner.answer('Ожидаем согласия участников отряда на вход на полигон (60 секунд).')
    except Exception:
        pending.finish()
        raise


def reply(owner, params):
    pending = getattr(owner, 'training_entry', None)
    if pending is not None:
        pending.reply(owner, params)


def cancel(owner):
    pending = getattr(owner, 'training_entry', None)
    if pending is not None:
        pending.finish('Вход на полигон отменён: участник вышел из игры.')
