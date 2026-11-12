"""Execute lazy installation, exact restoration and capability ordering in AVM1."""
import unittest

from avm_test import Arr, Function
import training_ground_client as client
import widescreen


class Bootstrap(unittest.TestCase):
    def environment(self, bootstrap_only=False):
        env = dict(_global={}, lol={}, Number=float, Boolean=bool,
                   mx=dict(utils=dict(Delegate=dict(create=lambda target, method: method))))
        originals = []
        for path, method, keep, helper, static in client.HOOKS:
            node = env['lol']
            for name in path:
                node = node.setdefault(name, {})
            if not static:
                node = node.setdefault('prototype', {})
            native = lambda *args: 'native'
            node[method] = native
            originals.append((node, method, keep, helper, native))
        package = client.patches(widescreen.Asm, widescreen.UNDEF)
        env['lol']['server']['XMLConnection']['getInstance'] = lambda: dict(connector=None)
        functions = {}
        for name, params, body in package['bootstrap' if bootstrap_only else 'globals']:
            functions[name] = env['_global'][name] = Function(params, body.assemble(), env)
        return env, functions, originals

    def test_only_two_transport_shims_are_eager_and_ui_helpers_stay_unallocated(self):
        env, f, originals = self.environment(bootstrap_only=True)
        package = client.patches(widescreen.Asm, widescreen.UNDEF)
        self.assertEqual([(path, method) for path, method, *_ in package['wraps']], [
            (('server', 'XMLConnection'), 'Send'),
            (('server', 'XMLConnection'), 'sendNotification')])
        self.assertNotIn('__tgText', env['_global'])
        self.assertNotIn('__tgInstall', env['_global'])
        for node, method, keep, helper, native in originals:
            self.assertIs(node[method], native)
            self.assertNotIn(keep, node)
        for name, _, body in package['bootstrap']:
            self.assertLess(len(body.assemble()), 65536, name)

    def test_types_require_a_compatible_hello_and_then_install_once(self):
        env, f, originals = self.environment(bootstrap_only=True)
        native_packets = []
        conn = dict(__tgNotifyOrig=lambda cmd: native_packets.append(cmd))
        notify = lambda cmd: f['__tgBootstrapNotify'].invoke(conn, [cmd])
        packet = dict(messID='tg', params=dict(op='types', copies=Arr()))
        notify(packet)
        self.assertNotIn('__tgInstall', env['_global'])
        for version, available in ((2, 1), (1, 0)):
            notify(dict(messID='tg', params=dict(op='hello', version=version, available=available)))
            notify(packet)
            self.assertNotIn('__tgInstall', env['_global'])
        notify(dict(messID='tg', params=dict(op='hello', version=1, available=1)))
        notify(packet)
        self.assertTrue(env['_global']['__tgHooksActive'])
        self.assertTrue(env['_global']['__tgActive'])
        self.assertIn('__tgText', env['_global'])
        first = [node[method] for node, method, *_ in originals]
        notify(packet)
        self.assertEqual([node[method] for node, method, *_ in originals], first)
        for node, method, keep, helper, native in originals:
            self.assertIs(node[keep], native)
            self.assertIs(node[method], env['_global'][helper])
        ordinary = dict(messID='userMove', params=dict(id=123))
        notify(ordinary)
        self.assertEqual(native_packets, [ordinary])

    def test_detach_restores_exact_method_chains_and_allows_reentry(self):
        env, f, originals = self.environment()
        for _ in range(3):
            f['__tgAttachHooks'].invoke(None, [])
            f['__tgAttachHooks'].invoke(None, [])
            f['__tgDetachHooks'].invoke(None, [])
            for node, method, keep, helper, native in originals:
                self.assertIs(node[method], native)
                self.assertNotIn(keep, node)
            self.assertFalse(env['_global']['__tgHooksActive'])

    def test_reentry_never_reuses_a_previous_inventory_callback_epoch(self):
        env, f, _ = self.environment()
        g, calls = env['_global'], []
        g['__tgEpoch'] = 40
        for epoch in (40, 41, 42):
            g['__tgEpoch'] = epoch
            f['__tgInstall'].invoke(None, [])
            self.assertEqual(g['__tgEpoch'], epoch)
            equipment = dict(ss_ack=lambda obj: calls.append(obj))
            f['__tgSnapshotAck'].invoke(equipment, [dict(data=dict(epoch=epoch - 1, mask=11))])
            self.assertEqual(calls, [])
            f['__tgDetachHooks'].invoke(None, [])

    def test_teardown_does_not_overwrite_a_later_method_owner(self):
        env, f, originals = self.environment()
        f['__tgAttachHooks'].invoke(None, [])
        node, method, keep, helper, native = originals[0]
        later = lambda: 'later'
        node[method] = later
        f['__tgDetachHooks'].invoke(None, [])
        self.assertIs(node[method], later)
        self.assertIs(node[keep], native)

    def test_private_suppliers_never_patch_native_trade_or_quantity_windows(self):
        env, f, _ = self.environment()
        native = lambda *args: 'native trade'
        windows = []
        for path, method in ((('gpui', 'TradeInterface'), 'createExchangePan'),
                             (('gpui', 'ExchangePan'), 'sendObj'),
                             (('core', 'player', 'Trade'), 'buy')):
            node = env['lol']
            for name in path:
                node = node.setdefault(name, {})
            proto = node.setdefault('prototype', {})
            proto[method] = native
            windows.append((proto, method))
        f['__tgAttachHooks'].invoke(None, [])
        for proto, method in windows:
            self.assertIs(proto[method], native)
        f['__tgDetachHooks'].invoke(None, [])
        for proto, method in windows:
            self.assertIs(proto[method], native)

    def transport(self):
        env, f, _ = self.environment()
        flag, sent = {'tg': False}, []
        manager = dict(getFlag=lambda name: flag.get(name),
                       setFlag=lambda name, value: flag.update({name: value}))
        conn = dict(__tgHandshakeOrig=lambda mess: sent.append(mess) or True)
        conn['Send'] = lambda mess: f['__tgHandshakeSend'].invoke(conn, [mess])
        def message():
            row = {}
            row['addProp'] = lambda name, value: row.update({name: value})
            return row
        env['lol']['server'].update(
            XMLConnection=dict(getInstance=lambda: conn),
            filters=dict(FilterManager=dict(getInstance=lambda: dict(currentFilter=manager))),
            mess=dict(CSMessage=message))
        return env, f, conn, flag, sent

    def test_hello_is_sent_before_character_activation_and_other_commands_pass_unchanged(self):
        for command in ('selPers', 'actPlayer'):
            with self.subTest(command=command):
                env, f, conn, flag, sent = self.transport()
                conn['__tgCompatible'] = True
                activate = dict(name=command, num=0)
                self.assertTrue(conn['Send'](activate))
                self.assertEqual(sent[0]['_name'], 'tg')
                self.assertEqual((sent[0]['op'], sent[0]['version']), ('@hello@', 1))
                self.assertIs(sent[1], activate)
                self.assertFalse(conn['__tgCompatible'])
                self.assertFalse(flag['tg'])
                move = dict(name='moveTo')
                self.assertTrue(conn['Send'](move))
                self.assertEqual(len(sent), 3)
                self.assertIs(sent[-1], move)

    def test_existing_character_login_negotiates_once_before_selection(self):
        env, f, conn, flag, sent = self.transport()
        commands = [dict(name=name) for name in
                    ('hello', 'login', 'selPers', 'lenter', 'gg_info', 'q_status')]
        # This is the existing-character path: there is no actPlayer packet.
        for command in commands:
            self.assertTrue(conn['Send'](command))
        self.assertEqual(sent[:2], commands[:2])
        self.assertEqual(sent[2]['_name'], 'tg')
        self.assertEqual(sent[2]['op'], '@hello@')
        self.assertEqual(sent[3:], commands[2:])
        self.assertFalse(flag['tg'])

    def test_send_failure_restores_both_previous_filter_states(self):
        env, f, conn, flag, _ = self.transport()
        def fail(mess):
            self.assertTrue(flag['tg'])
            raise OSError('lost connection')
        conn['Send'] = fail
        for previous in (False, True):
            flag['tg'] = previous
            with self.assertRaises(OSError):
                f['__tgTransmit'].invoke(None, [{}])
            self.assertIs(flag['tg'], previous)

    def test_return_waits_for_both_stats_and_equipment_before_detaching(self):
        env, f, _ = self.environment()
        g, events = env['_global'], []
        equipment = dict(__tgManaged=True)
        env['lol']['core']['Master']['getInstance'] = lambda: dict(gamer=dict(equipment=equipment))
        g.update(__tgHooksActive=True, __tgActive=False, __tgReturnEquipment=True,
                 __tgSnapshotPending=True, __tgReturnBagPending=True,
                 __tgForgetItems=lambda force: events.append('forget'),
                 __tgDetachHooks=lambda: events.append('detach'))
        for key in ('__tgReturnEquipment', '__tgSnapshotPending', '__tgReturnBagPending'):
            f['__tgMaybeDetach'].invoke(None, [])
            self.assertEqual(events, [])
            g[key] = False
        f['__tgMaybeDetach'].invoke(None, [])
        self.assertEqual(events, ['forget', 'detach'])
        self.assertFalse(equipment['__tgManaged'])

    def test_disconnect_can_detach_aliases_before_calling_original_close(self):
        env, f, _ = self.environment()
        for name, alias in (('__tgConnectionCloseWrapper', '__tgConnectionCloseOrig'),
                            ('__tgSocketWrapper', '__tgSocketOrig')):
            events = []
            conn = {alias: lambda: events.append('native')}
            env['_global']['__tgCleanup'] = lambda: (events.append('cleanup'), conn.pop(alias))
            f[name].invoke(conn, [])
            self.assertEqual(events, ['cleanup', 'native'])

    def test_existing_socket_delegate_is_rebound_and_restored_without_changing_other_listeners(self):
        env, f, _ = self.environment()
        events = []
        native = lambda: events.append('native delegate')
        current = lambda: events.append('range close')
        socket = dict(onClose=native, onXML='unchanged')
        env['lol']['server']['XMLConnection']['getInstance'] = lambda: dict(connector=socket, onClose=current)
        env['mx'] = dict(utils=dict(Delegate=dict(create=lambda target, method: method)))
        f['__tgBindSocket'].invoke(None, [])
        self.assertIs(socket['onClose'], current)
        socket['onClose']()
        self.assertEqual(events, ['range close'])
        f['__tgUnbindSocket'].invoke(None, [])
        self.assertIs(socket['onClose'], native)
        self.assertEqual(socket['onXML'], 'unchanged')
        self.assertIsNone(env['_global']['__tgSocketTarget'])


if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
    from testkit import run_cases
    run_cases(Bootstrap)
