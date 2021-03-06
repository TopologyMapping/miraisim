import logging

import hosts

import sim


STATUS_ACTIVE = 'bot_status_active'
STATUS_CREATED = 'bot_status_created'
STATUS_TEARDOWN = 'bot_status_teardown'


def create_factory(config):
    name = config['bot']['class']
    if name not in globals():
        msg = 'unknown bot behavior (%s)' % name
        logging.fatal(msg)
        raise ValueError(msg)
    return globals()[name].Factory(config)


class FixedRateMixin(object):  # {{{
    def __init__(self, rate):
        self.rate = float(rate)

    def start(self):
        ev = (sim.now, self.attempt_auth, None)
        sim.enqueue(ev)

    def attempt_auth_begin(self):
        ev = (sim.now + 1/self.rate, self.attempt_auth, None)
        sim.enqueue(ev)

    def attempt_auth_success(self, delay, hid):
        ev = (sim.now + delay, self.attempt_infect, hid)
        sim.enqueue(ev)

    def attempt_auth_failure(self, _delay):
        pass

    def attempt_infect_end(self, _delay):
        pass
# }}}


class MultithreadMixin(object):  # {{{
    def __init__(self, nthreads):
        self.nthreads = int(nthreads)

    def start(self):
        for _i in range(self.nthreads):
            ev = (sim.now, self.attempt_auth, None)
            sim.enqueue(ev)

    def attempt_auth_begin(self):
        pass

    def attempt_auth_success(self, delay, hid):
        ev = (sim.now + delay, self.attempt_infect, hid)
        sim.enqueue(ev)

    def attempt_auth_failure(self, delay):
        ev = (sim.now + delay, self.attempt_auth, None)
        sim.enqueue(ev)

    def attempt_infect_end(self, delay):
        ev = (sim.now + delay, self.attempt_auth, None)
        sim.enqueue(ev)
# }}}


class BotMixin(object):  # {{{
    def __init__(self):
        self.targeting = sim.targeting_factory()  # pylint: disable=not-callable
        self.status = STATUS_CREATED

    def start(self):
        super().start()
        assert self.status == STATUS_CREATED
        self.status = STATUS_ACTIVE

    def attempt_auth(self, _data):
        logging.debug('%s entering', self)
        if self.status == STATUS_TEARDOWN:
            logging.debug('%s teardown abort', self)
            return

        self.attempt_auth_begin()

        dsthid = self.targeting.get_target()
        _host, status = sim.host_tracker.get(dsthid)
        logging.debug('%s dst %d status %s', self, dsthid, status)

        if status in [hosts.STATUS_SECURE,
                      hosts.STATUS_SHUTDOWN,
                      hosts.STATUS_INFECTED]:
            delay = sim.e2e_latency.get_timeout()
            self.targeting.set_unreach(dsthid)
            self.attempt_auth_failure(delay)
        elif status in [hosts.STATUS_VULNERABLE]:
            # cunha @20180111.1335 not sure we need this FIXME
            # include infect delay:
            # delay += sim.e2e_latency.get_infect_delay(self.hid, dsthid)
            delay = sim.e2e_latency.get_auth_delay(self.hid, dsthid)
            self.attempt_auth_success(delay, dsthid)

    def attempt_infect(self, hid):
        logging.debug('%s entering', self)
        if self.status == STATUS_TEARDOWN:
            logging.debug('%s teardown abort', self)
            return

        host, status = sim.host_tracker.get(hid)
        logging.debug('%s dst %d status %s', self, hid, status)

        if hid in self.targeting:
            logging.debug('%s dst %d in-cache abort', self, hid)
            delay = 0
        elif status in [hosts.STATUS_SECURE,
                        hosts.STATUS_SHUTDOWN,
                        hosts.STATUS_INFECTED]:
            logging.debug('%s dst %d unreachable failure', self, hid)
            self.targeting.set_unreach(hid)
            delay = sim.e2e_latency.get_timeout()
        elif status in [hosts.STATUS_VULNERABLE]:
            logging.info('%s dst %d infect success', self, hid)
            self.targeting.set_bot(hid)
            host.infect()
            delay = sim.e2e_latency.get_infect_delay(self.hid, hid)

        self.attempt_infect_end(delay)

    def teardown(self):
        assert self.status == STATUS_ACTIVE
        self.status = STATUS_TEARDOWN

    def __str__(self):
        return 'Bot %d' % self.hid
# }}}


class FixedRateBot(BotMixin, FixedRateMixin):  # {{{
    class Factory(object):  # {{{
        def __init__(self, config):
            assert len(config['bot']['params']) == 1
            self.rate = float(config['bot']['params'][0])

        def __call__(self, hid):
            return FixedRateBot(hid, self.rate)
    # }}}

    def __init__(self, hid, rate):
        BotMixin.__init__(self)
        FixedRateMixin.__init__(self, rate)
        self.hid = int(hid)
        logging.debug('%s rate %f', self, self.rate)
# }}}


class MultithreadBot(BotMixin, MultithreadMixin):  # {{{
    class Factory(object):  # {{{
        def __init__(self, config):
            assert len(config['bot']['params']) == 1
            self.nthreads = float(config['bot']['params'][0])

        def __call__(self, hid):
            return MultithreadBot(hid, self.nthreads)
    # }}}

    def __init__(self, hid, nthreads):
        BotMixin.__init__(self)
        MultithreadMixin.__init__(self, nthreads)
        self.hid = int(hid)
        logging.debug('%s nthreads %d', self, self.nthreads)
# }}}
