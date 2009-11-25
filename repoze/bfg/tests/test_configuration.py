import unittest

from repoze.bfg import testing

class ConfiguratorTests(unittest.TestCase):
    def _makeOne(self, *arg, **kw):
        from repoze.bfg.configuration import Configurator
        return Configurator(*arg, **kw)

    def _registerRenderer(self, config, name='.txt'):
        from repoze.bfg.interfaces import IRendererFactory
        from repoze.bfg.interfaces import ITemplateRenderer
        from zope.interface import implements
        class Renderer:
            implements(ITemplateRenderer)
            def __init__(self, path):
                self.__class__.path = path
            def __call__(self, *arg):
                return 'Hello!'
        config.registry.registerUtility(Renderer, IRendererFactory, name=name)
        return Renderer

    def _getViewCallable(self, config, ctx_iface=None, request_iface=None,
                         name=''):
        from zope.interface import Interface
        from repoze.bfg.interfaces import IRequest
        from repoze.bfg.interfaces import IView
        if ctx_iface is None:
            ctx_iface = Interface
        if request_iface is None:
            request_iface = IRequest
        return config.registry.adapters.lookup(
            (ctx_iface, request_iface), IView, name=name,
            default=None)

    def _getRouteRequestIface(self, config, name):
        from repoze.bfg.interfaces import IRouteRequest
        iface = config.registry.getUtility(IRouteRequest, name)
        return iface

    def _assertNotFound(self, wrapper, *arg):
        from repoze.bfg.exceptions import NotFound
        self.assertRaises(NotFound, wrapper, *arg)

    def _registerEventListener(self, config, event_iface=None):
        """ Registers an event listener (aka 'subscriber') listening for
        events of the type ``event_iface`` and returns a list which is
        appended to by the subscriber.  When an event is dispatched that
        matches ``event_iface``, that event will be appended to the list.
        You can then compare the values in the list to expected event
        notifications.  This method is useful when testing code that wants
        to call ``zope.component.event.dispatch`` or
        ``zope.component.event.objectEventNotify``."""
        if event_iface is None: # pragma: no cover
            from zope.interface import Interface
            event_iface = Interface
        L = []
        def subscriber(*event):
            L.extend(event)
        config.registry.registerHandler(subscriber, (event_iface,))
        return L

    def _registerLogger(self, config):
        from repoze.bfg.interfaces import IDebugLogger
        logger = DummyLogger()
        config.registry.registerUtility(logger, IDebugLogger)
        return logger

    def _makeRequest(self, config):
        request = DummyRequest()
        request.registry = config.registry
        return request

    def _registerSecurityPolicy(self, config, permissive):
        from repoze.bfg.interfaces import IAuthenticationPolicy
        from repoze.bfg.interfaces import IAuthorizationPolicy
        policy = DummySecurityPolicy(permissive)
        config.registry.registerUtility(policy, IAuthenticationPolicy)
        config.registry.registerUtility(policy, IAuthorizationPolicy)

    def _registerSettings(self, config, **settings):
        from repoze.bfg.interfaces import ISettings
        config.registry.registerUtility(settings, ISettings)

    def test_ctor_no_registry(self):
        import sys
        from repoze.bfg.interfaces import ISettings
        from repoze.bfg.configuration import Configurator
        from repoze.bfg.interfaces import IRendererFactory
        config = Configurator()
        this_pkg = sys.modules['repoze.bfg.tests']
        self.failUnless(config.registry.getUtility(ISettings))
        self.assertEqual(config.package, this_pkg)
        self.failUnless(config.registry.getUtility(IRendererFactory, 'json'))

    def test_ctor_with_package_registry(self):
        import sys
        from repoze.bfg.configuration import Configurator
        bfg_pkg = sys.modules['repoze.bfg']
        config = Configurator(package=bfg_pkg)
        self.assertEqual(config.package, bfg_pkg)

    def test_ctor_noreg_zcml_file(self):
        config = self._makeOne(
            registry=None,
            zcml_file='repoze.bfg.tests.fixtureapp:configure.zcml')
        registry = config.registry
        from repoze.bfg.tests.fixtureapp.models import IFixture
        self.failUnless(registry.queryUtility(IFixture)) # only in c.zcml

    def test_ctor_noreg_zcml_file_routes_in_config(self):
        from repoze.bfg.interfaces import IRoutesMapper
        config = self._makeOne(
            zcml_file='repoze.bfg.tests.routesapp:configure.zcml')
        self.failUnless(config.registry.getUtility(IRoutesMapper))

    def test_ctor_noreg_custom_settings(self):
        from repoze.bfg.interfaces import ISettings
        settings = {'reload_templates':True,
                    'mysetting':True}
        config = self._makeOne(settings=settings)
        settings = config.registry.getUtility(ISettings)
        self.assertEqual(settings['reload_templates'], True)
        self.assertEqual(settings['debug_authorization'], False)
        self.assertEqual(settings['mysetting'], True)

    def test_ctor_noreg_debug_logger_None_default(self):
        from repoze.bfg.interfaces import IDebugLogger
        config = self._makeOne()
        logger = config.registry.getUtility(IDebugLogger)
        self.assertEqual(logger.name, 'repoze.bfg.debug')

    def test_ctor_noreg_debug_logger_non_None(self):
        from repoze.bfg.interfaces import IDebugLogger
        logger = object()
        config = self._makeOne(debug_logger=logger)
        result = config.registry.getUtility(IDebugLogger)
        self.assertEqual(logger, result)

    def test_ctor_authentication_policy(self):
        from repoze.bfg.interfaces import IAuthenticationPolicy
        policy = object()
        config = self._makeOne(authentication_policy=policy)
        result = config.registry.getUtility(IAuthenticationPolicy)
        self.assertEqual(policy, result)

    def test_ctor_no_root_factory(self):
        from repoze.bfg.interfaces import IRootFactory
        config = self._makeOne()
        self.failUnless(config.registry.getUtility(IRootFactory))

    def test_ctor_alternate_renderers(self):
        from repoze.bfg.interfaces import IRendererFactory
        renderer = object()
        config = self._makeOne(renderers=[('yeah', renderer)])
        self.assertEqual(config.registry.getUtility(IRendererFactory, 'yeah'),
                         renderer)

    def test_ctor_hook_zca_true(self):
        from zope.component import getSiteManager
        from repoze.bfg.threadlocal import get_current_registry
        try:
            getSiteManager.reset()
            config = self._makeOne(hook_zca=True)
            hooked = getSiteManager.sethook(None)
            self.assertEqual(hooked, get_current_registry)
        finally:
            getSiteManager.reset()

    def test_ctor_hook_zca_false(self):
        from zope.component import getSiteManager
        from repoze.bfg.threadlocal import get_current_registry
        try:
            getSiteManager.reset()
            config = self._makeOne(hook_zca=False)
            hooked = getSiteManager.sethook(None)
            self.failIfEqual(hooked, get_current_registry)
        finally:
            getSiteManager.reset()

    def test_ctor_hook_zca_default_false(self):
        from zope.component import getSiteManager
        from repoze.bfg.threadlocal import get_current_registry
        try:
            getSiteManager.reset()
            config = self._makeOne()
            hooked = getSiteManager.sethook(None)
            self.failIfEqual(hooked, get_current_registry)
        finally:
            getSiteManager.reset()

    def test_add_subscriber_defaults(self):
        from zope.interface import implements
        from zope.interface import Interface
        class IEvent(Interface):
            pass
        class Event:
            implements(IEvent)
        L = []
        def subscriber(event):
            L.append(event)
        config = self._makeOne()
        config.add_subscriber(subscriber)
        event = Event()
        config.registry.notify(event)
        self.assertEqual(len(L), 1)
        self.assertEqual(L[0], event)
        config.registry.notify(object())
        self.assertEqual(len(L), 2)

    def test_add_subscriber_iface_specified(self):
        from zope.interface import implements
        from zope.interface import Interface
        class IEvent(Interface):
            pass
        class Event:
            implements(IEvent)
        L = []
        def subscriber(event):
            L.append(event)
        config = self._makeOne()
        config.add_subscriber(subscriber, IEvent)
        event = Event()
        config.registry.notify(event)
        self.assertEqual(len(L), 1)
        self.assertEqual(L[0], event)
        config.registry.notify(object())
        self.assertEqual(len(L), 1)

    def test_add_object_event_subscriber(self):
        from zope.interface import implements
        from zope.interface import Interface
        class IEvent(Interface):
            pass
        class Event:
            object = 'foo'
            implements(IEvent)
        event = Event()
        L = []
        def subscriber(object, event):
            L.append(event)
        config = self._makeOne()
        config.add_subscriber(subscriber, (Interface, IEvent))
        config.registry.subscribers((event.object, event), None)
        self.assertEqual(len(L), 1)
        self.assertEqual(L[0], event)
        config.registry.subscribers((event.object, IDummy), None)
        self.assertEqual(len(L), 1)
        
    def test_make_wsgi_app(self):
        from repoze.bfg.router import Router
        from repoze.bfg.interfaces import IWSGIApplicationCreatedEvent
        class ThreadLocalManager(object):
            def push(self, d):
                self.pushed = d
            def pop(self):
                self.popped = True
        manager = ThreadLocalManager()
        config = self._makeOne()
        subscriber = self._registerEventListener(config,
                                                 IWSGIApplicationCreatedEvent)
        app = config.make_wsgi_app(manager=manager)
        self.assertEqual(app.__class__, Router)
        self.assertEqual(manager.pushed['registry'], config.registry)
        self.assertEqual(manager.pushed['request'], None)
        self.failUnless(manager.popped)
        self.assertEqual(len(subscriber), 1)

    def test_load_zcml_default(self):
        import repoze.bfg.tests.fixtureapp
        config = self._makeOne(package=repoze.bfg.tests.fixtureapp)
        registry = config.load_zcml()
        from repoze.bfg.tests.fixtureapp.models import IFixture
        self.failUnless(registry.queryUtility(IFixture)) # only in c.zcml

    def test_load_zcml_as_resource_spec(self):
        config = self._makeOne()
        registry = config.load_zcml(
            'repoze.bfg.tests.fixtureapp:configure.zcml')
        from repoze.bfg.tests.fixtureapp.models import IFixture
        self.failUnless(registry.queryUtility(IFixture)) # only in c.zcml

    def test_load_zcml_as_relative_filename(self):
        import repoze.bfg.tests.fixtureapp
        config = self._makeOne(package=repoze.bfg.tests.fixtureapp)
        registry = config.load_zcml('configure.zcml')
        from repoze.bfg.tests.fixtureapp.models import IFixture
        self.failUnless(registry.queryUtility(IFixture)) # only in c.zcml

    def test_load_zcml_as_absolute_filename(self):
        import os
        import repoze.bfg.tests.fixtureapp
        config = self._makeOne(package=repoze.bfg.tests.fixtureapp)
        dn = os.path.dirname(repoze.bfg.tests.fixtureapp.__file__)
        c_z = os.path.join(dn, 'configure.zcml')
        registry = config.load_zcml(c_z)
        from repoze.bfg.tests.fixtureapp.models import IFixture
        self.failUnless(registry.queryUtility(IFixture)) # only in c.zcml

    def test_load_zcml_lock_and_unlock(self):
        config = self._makeOne()
        dummylock = DummyLock()
        registry = config.load_zcml(
            'repoze.bfg.tests.fixtureapp:configure.zcml',
            lock=dummylock)
        self.assertEqual(dummylock.acquired, True)
        self.assertEqual(dummylock.released, True)

    def test_add_view_view_callable_None_no_renderer(self):
        from zope.configuration.exceptions import ConfigurationError
        config = self._makeOne()
        self.assertRaises(ConfigurationError, config.add_view)

    def test_add_view_with_request_type_and_route_name(self):
        from zope.configuration.exceptions import ConfigurationError
        config = self._makeOne()
        view = lambda *arg: 'OK'
        self.assertRaises(ConfigurationError, config.add_view, view, '', None,
                          None, True, True)

    def test_add_view_view_callable_None_with_renderer(self):
        config = self._makeOne()
        self._registerRenderer(config, name='dummy')
        config.add_view(renderer='dummy')
        view = self._getViewCallable(config)
        self.failUnless('Hello!' in view(None, None).body)

    def test_add_view_wrapped_view_is_decorated(self):
        def view(request): # request-only wrapper
            """ """
        config = self._makeOne()
        config.add_view(view=view)
        wrapper = self._getViewCallable(config)
        self.assertEqual(wrapper.__module__, view.__module__)
        self.assertEqual(wrapper.__name__, view.__name__)
        self.assertEqual(wrapper.__doc__, view.__doc__)

    def test_add_view_with_function_callable(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view)
        wrapper = self._getViewCallable(config)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_with_function_callable_requestonly(self):
        def view(request):
            return 'OK'
        config = self._makeOne()
        config.add_view(view=view)
        wrapper = self._getViewCallable(config)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_as_instance(self):
        class AView:
            def __call__(self, context, request):
                """ """
                return 'OK'
        view = AView()
        config = self._makeOne()
        config.add_view(view=view)
        wrapper = self._getViewCallable(config)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_as_instance_requestonly(self):
        class AView:
            def __call__(self, request):
                """ """
                return 'OK'
        view = AView()
        config = self._makeOne()
        config.add_view(view=view)
        wrapper = self._getViewCallable(config)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_as_oldstyle_class(self):
        class view:
            def __init__(self, context, request):
                self.context = context
                self.request = request

            def __call__(self):
                return 'OK'
        config = self._makeOne()
        config.add_view(view=view)
        wrapper = self._getViewCallable(config)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_as_oldstyle_class_requestonly(self):
        class view:
            def __init__(self, request):
                self.request = request

            def __call__(self):
                return 'OK'
        config = self._makeOne()
        config.add_view(view=view)
        wrapper = self._getViewCallable(config)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_for_as_class(self):
        from zope.interface import implementedBy
        view = lambda *arg: 'OK'
        class Foo:
            pass
        config = self._makeOne()
        config.add_view(for_=Foo, view=view)
        foo = implementedBy(Foo)
        wrapper = self._getViewCallable(config, foo)
        self.assertEqual(wrapper, view)

    def test_add_view_for_as_iface(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(for_=IDummy, view=view)
        wrapper = self._getViewCallable(config, IDummy)
        self.assertEqual(wrapper, view)

    def test_add_view_register_secured_view(self):
        from zope.interface import Interface
        from repoze.bfg.interfaces import IRequest
        from repoze.bfg.interfaces import ISecuredView
        view = lambda *arg: 'OK'
        view.__call_permissive__ = view
        config = self._makeOne()
        config.add_view(view=view)
        wrapper = config.registry.adapters.lookup(
            (Interface, IRequest), ISecuredView, name='', default=None)
        self.assertEqual(wrapper, view)

    def test_add_view_multiview_replaces_existing_view(self):
        from zope.interface import Interface
        from repoze.bfg.interfaces import IRequest
        from repoze.bfg.interfaces import IView
        from repoze.bfg.interfaces import IMultiView
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.registry.registerAdapter(
            view, (Interface, IRequest), IView, name='')
        config.add_view(view=view)
        wrapper = self._getViewCallable(config)
        self.failUnless(IMultiView.providedBy(wrapper))
        self.assertEqual(wrapper(None, None), 'OK')

    def test_add_view_multiview_replaces_multiview(self):
        from zope.interface import Interface
        from zope.interface import implements
        from repoze.bfg.interfaces import IRequest
        from repoze.bfg.interfaces import IMultiView
        class DummyMultiView:
            implements(IMultiView)
            def __init__(self):
                self.views = []
                self.name = 'name'
            def add(self, view, score):
                self.views.append(view)
            def __call__(self, context, request):
                return 'OK1'
            def __permitted__(self, context, request):
                """ """
        view = DummyMultiView()
        config = self._makeOne()
        config.registry.registerAdapter(view, (Interface, IRequest),
                                        IMultiView, name='')
        view2 = lambda *arg: 'OK2'
        config.add_view(view=view2)
        wrapper = self._getViewCallable(config)
        self.failUnless(IMultiView.providedBy(wrapper))
        self.assertEqual(wrapper.views, [view2])
        self.assertEqual(wrapper(None, None), 'OK1')

    def test_add_view_multiview_call_ordering(self):
        from zope.interface import directlyProvides
        def view1(context, request): return 'view1'
        def view2(context, request): return 'view2'
        def view3(context, request): return 'view3'
        def view4(context, request): return 'view4'
        def view5(context, request): return 'view5'
        def view6(context, request): return 'view6'
        def view7(context, request): return 'view7'
        def view8(context, request): return 'view8'
        config = self._makeOne()
        config.add_view(view=view1)
        config.add_view(view=view2, request_method='POST')
        config.add_view(view=view3,request_param='param')
        config.add_view(view=view4, containment=IDummy)
        config.add_view(view=view5, request_method='POST',request_param='param')
        config.add_view(view=view6, request_method='POST', containment=IDummy)
        config.add_view(view=view7, request_param='param', containment=IDummy)
        config.add_view(view=view8, request_method='POST',request_param='param',
                        containment=IDummy)

        wrapper = self._getViewCallable(config)

        ctx = DummyContext()
        request = self._makeRequest(config)
        request.method = 'GET'
        request.params = {}
        self.assertEqual(wrapper(ctx, request), 'view1')

        ctx = DummyContext()
        request = self._makeRequest(config)
        request.params = {}
        request.method = 'POST'
        self.assertEqual(wrapper(ctx, request), 'view2')

        ctx = DummyContext()
        request = self._makeRequest(config)
        request.params = {'param':'1'}
        request.method = 'GET'
        self.assertEqual(wrapper(ctx, request), 'view3')

        ctx = DummyContext()
        directlyProvides(ctx, IDummy)
        request = self._makeRequest(config)
        request.method = 'GET'
        request.params = {}
        self.assertEqual(wrapper(ctx, request), 'view4')

        ctx = DummyContext()
        request = self._makeRequest(config)
        request.method = 'POST'
        request.params = {'param':'1'}
        self.assertEqual(wrapper(ctx, request), 'view5')

        ctx = DummyContext()
        directlyProvides(ctx, IDummy)
        request = self._makeRequest(config)
        request.params = {}
        request.method = 'POST'
        self.assertEqual(wrapper(ctx, request), 'view6')

        ctx = DummyContext()
        directlyProvides(ctx, IDummy)
        request = self._makeRequest(config)
        request.method = 'GET'
        request.params = {'param':'1'}
        self.assertEqual(wrapper(ctx, request), 'view7')

        ctx = DummyContext()
        directlyProvides(ctx, IDummy)
        request = self._makeRequest(config)
        request.method = 'POST'
        request.params = {'param':'1'}
        self.assertEqual(wrapper(ctx, request), 'view8')

    def test_add_view_with_template_renderer(self):
        class view(object):
            def __init__(self, context, request):
                self.request = request
                self.context = context

            def __call__(self):
                return {'a':'1'}
        config = self._makeOne()
        renderer = self._registerRenderer(config)
        fixture = 'repoze.bfg.tests:fixtures/minimal.txt'
        config.add_view(view=view, renderer=fixture)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        result = wrapper(None, request)
        self.assertEqual(result.body, 'Hello!')
        self.assertEqual(renderer.path, 'repoze.bfg.tests:fixtures/minimal.txt')

    def test_add_view_with_template_renderer_no_callable(self):
        config = self._makeOne()
        renderer = self._registerRenderer(config)
        fixture = 'repoze.bfg.tests:fixtures/minimal.txt'
        config.add_view(view=None, renderer=fixture)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        result = wrapper(None, request)
        self.assertEqual(result.body, 'Hello!')
        self.assertEqual(renderer.path, 'repoze.bfg.tests:fixtures/minimal.txt')

    def test_add_view_with_request_type_as_iface(self):
        def view(context, request):
            return 'OK'
        config = self._makeOne()
        config.add_view(request_type=IDummy, view=view)
        wrapper = self._getViewCallable(config, None, IDummy)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_with_request_type_as_noniface(self):
        from zope.interface import providedBy
        def view(context, request):
            return 'OK'
        config = self._makeOne()
        config.add_view(request_type=object, view=view)
        request_iface = providedBy(object)
        wrapper = self._getViewCallable(config, None, request_iface)
        result = wrapper(None, None)
        self.assertEqual(result, 'OK')

    def test_add_view_with_route_name(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, route_name='foo')
        request_type = self._getRouteRequestIface(config, 'foo')
        wrapper = self._getViewCallable(config, None, request_type)
        self.assertEqual(wrapper(None, None), 'OK')

    def test_add_view_with_request_method_true(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, request_method='POST')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.method = 'POST'
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_request_method_false(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, request_method='POST')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.method = 'GET'
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_request_param_noval_true(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, request_param='abc')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.params = {'abc':''}
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_request_param_noval_false(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, request_param='abc')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.params = {}
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_request_param_val_true(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, request_param='abc=123')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.params = {'abc':'123'}
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_request_param_val_false(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, request_param='abc=123')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.params = {'abc':''}
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_xhr_true(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, xhr=True)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.is_xhr = True
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_xhr_false(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, xhr=True)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.is_xhr = False
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_header_badregex(self):
        from zope.configuration.exceptions import ConfigurationError
        view = lambda *arg: 'OK'
        config = self._makeOne()
        self.assertRaises(ConfigurationError,
                          config.add_view, view=view, header='Host:a\\')

    def test_add_view_with_header_noval_match(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, header='Host')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.headers = {'Host':'whatever'}
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_header_noval_nomatch(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, header='Host')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.headers = {'NotHost':'whatever'}
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_header_val_match(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, header=r'Host:\d')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.headers = {'Host':'1'}
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_header_val_nomatch(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, header=r'Host:\d')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.headers = {'Host':'abc'}
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_accept_match(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, accept='text/xml')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.accept = ['text/xml']
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_accept_nomatch(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, accept='text/xml')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.accept = ['text/html']
        self._assertNotFound(wrapper, None, request)

    def test_add_view_with_containment_true(self):
        from zope.interface import directlyProvides
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, containment=IDummy)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        context = DummyContext()
        directlyProvides(context, IDummy)
        self.assertEqual(wrapper(context, None), 'OK')

    def test_add_view_with_containment_false(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, containment=IDummy)
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        context = DummyContext()
        self._assertNotFound(wrapper, context, None)

    def test_add_view_with_path_info_badregex(self):
        from zope.configuration.exceptions import ConfigurationError
        view = lambda *arg: 'OK'
        config = self._makeOne()
        self.assertRaises(ConfigurationError,
                          config.add_view, view=view, path_info='\\')

    def test_add_view_with_path_info_match(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, path_info='/foo')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.path_info = '/foo'
        self.assertEqual(wrapper(None, request), 'OK')

    def test_add_view_with_path_info_nomatch(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        config.add_view(view=view, path_info='/foo')
        wrapper = self._getViewCallable(config)
        request = self._makeRequest(config)
        request.path_info = '/'
        self._assertNotFound(wrapper, None, request)

    def _assertRoute(self, config, name, path, num_predicates=0):
        from repoze.bfg.interfaces import IRoutesMapper
        mapper = config.registry.getUtility(IRoutesMapper)
        routes = mapper.get_routes()
        route = routes[0]
        self.assertEqual(len(routes), 1)
        self.assertEqual(route.name, name)
        self.assertEqual(route.path, path)
        self.assertEqual(len(routes[0].predicates), num_predicates)
        return route

    def test_add_route_defaults(self):
        config = self._makeOne()
        config.add_route('name', 'path')
        self._assertRoute(config, 'name', 'path')

    def test_add_route_with_xhr(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', xhr=True)
        request_type = self._getRouteRequestIface(config, 'name')
        route = self._assertRoute(config, 'name', 'path', 1)
        predicate = route.predicates[0]
        request = self._makeRequest(config)
        request.is_xhr = True
        self.assertEqual(predicate(None, request), True)
        request = self._makeRequest(config)
        request.is_xhr = False
        self.assertEqual(predicate(None, request), False)

    def test_add_route_with_request_method(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', request_method='GET')
        request_type = self._getRouteRequestIface(config, 'name')
        route = self._assertRoute(config, 'name', 'path', 1)
        predicate = route.predicates[0]
        request = self._makeRequest(config)
        request.method = 'GET'
        self.assertEqual(predicate(None, request), True)
        request = self._makeRequest(config)
        request.method = 'POST'
        self.assertEqual(predicate(None, request), False)

    def test_add_route_with_path_info(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', path_info='/foo')
        request_type = self._getRouteRequestIface(config, 'name')
        route = self._assertRoute(config, 'name', 'path', 1)
        predicate = route.predicates[0]
        request = self._makeRequest(config)
        request.path_info = '/foo'
        self.assertEqual(predicate(None, request), True)
        request = self._makeRequest(config)
        request.path_info = '/'
        self.assertEqual(predicate(None, request), False)

    def test_add_route_with_request_param(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', request_param='abc')
        request_type = self._getRouteRequestIface(config, 'name')
        route = self._assertRoute(config, 'name', 'path', 1)
        predicate = route.predicates[0]
        request = self._makeRequest(config)
        request.params = {'abc':'123'}
        self.assertEqual(predicate(None, request), True)
        request = self._makeRequest(config)
        request.params = {}
        self.assertEqual(predicate(None, request), False)

    def test_add_route_with_header(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', header='Host')
        request_type = self._getRouteRequestIface(config, 'name')
        route = self._assertRoute(config, 'name', 'path', 1)
        predicate = route.predicates[0]
        request = self._makeRequest(config)
        request.headers = {'Host':'example.com'}
        self.assertEqual(predicate(None, request), True)
        request = self._makeRequest(config)
        request.headers = {}
        self.assertEqual(predicate(None, request), False)

    def test_add_route_with_accept(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', accept='text/xml')
        request_type = self._getRouteRequestIface(config, 'name')
        route = self._assertRoute(config, 'name', 'path', 1)
        predicate = route.predicates[0]
        request = self._makeRequest(config)
        request.accept = ['text/xml']
        self.assertEqual(predicate(None, request), True)
        request = self._makeRequest(config)
        request.accept = ['text/html']
        self.assertEqual(predicate(None, request), False)

    def test_add_route_with_view(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view)
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, None, request_type)
        self.assertEqual(wrapper(None, None), 'OK')
        self._assertRoute(config, 'name', 'path')

    def test_add_route_with_view_for(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view, view_for=IDummy)
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, IDummy, request_type)
        self.assertEqual(wrapper(None, None), 'OK')
        self._assertRoute(config, 'name', 'path')
        wrapper = self._getViewCallable(config, IOther, request_type)
        self.assertEqual(wrapper, None)

    def test_add_route_with_view_for_alias(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view, for_=IDummy)
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, IDummy, request_type)
        self.assertEqual(wrapper(None, None), 'OK')
        self._assertRoute(config, 'name', 'path')
        wrapper = self._getViewCallable(config, IOther, request_type)
        self.assertEqual(wrapper, None)

    def test_add_route_with_view_request_method(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view, view_request_method='GET')
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, None, request_type)
        route = self._assertRoute(config, 'name', 'path')
        request = self._makeRequest(config)
        request.method = 'GET'
        self.assertEqual(wrapper(None, request), 'OK')
        request = self._makeRequest(config)
        request.method = 'POST'
        self._assertNotFound(wrapper, None, request)

    def test_add_route_with_view_header(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view, view_header='Host')
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, None, request_type)
        route = self._assertRoute(config, 'name', 'path')
        request = self._makeRequest(config)
        request.headers = {'Host':'abc'}
        self.assertEqual(wrapper(None, request), 'OK')
        request = self._makeRequest(config)
        request.headers = {}
        self._assertNotFound(wrapper, None, request)

    def test_add_route_with_view_xhr(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view, view_xhr=True)
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, None, request_type)
        route = self._assertRoute(config, 'name', 'path')
        request = self._makeRequest(config)
        request.is_xhr = True
        self.assertEqual(wrapper(None, request), 'OK')
        request = self._makeRequest(config)
        request.is_xhr = False
        self._assertNotFound(wrapper, None, request)

    def test_add_route_with_view_path_info(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view, view_path_info='/foo')
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, None, request_type)
        route = self._assertRoute(config, 'name', 'path')
        request = self._makeRequest(config)
        request.path_info = '/foo'
        self.assertEqual(wrapper(None, request), 'OK')
        request = self._makeRequest(config)
        request.path_info = '/'
        self._assertNotFound(wrapper, None, request)

    def test_add_route_with_view_accept(self):
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view, view_accept='text/xml')
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, None, request_type)
        route = self._assertRoute(config, 'name', 'path')
        request = self._makeRequest(config)
        request.accept = ['text/xml']
        self.assertEqual(wrapper(None, request), 'OK')
        request = self._makeRequest(config)
        request.accept = ['text/html']
        self._assertNotFound(wrapper, None, request)

    def test_add_route_with_view_containment(self):
        from zope.interface import directlyProvides
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view, view_containment=IDummy)
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, None, request_type)
        route = self._assertRoute(config, 'name', 'path')
        context = DummyContext()
        directlyProvides(context, IDummy)
        self.assertEqual(wrapper(context, None), 'OK')
        self._assertNotFound(wrapper, None, None)

    def test_add_route_with_view_renderer(self):
        config = self._makeOne()
        self._registerRenderer(config)
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view,
                         view_renderer='fixtures/minimal.txt')
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, None, request_type)
        route = self._assertRoute(config, 'name', 'path')
        self.assertEqual(wrapper(None, None).body, 'Hello!')

    def test_add_route_with_view_renderer_alias(self):
        config = self._makeOne()
        self._registerRenderer(config)
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view,
                         renderer='fixtures/minimal.txt')
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, None, request_type)
        route = self._assertRoute(config, 'name', 'path')
        self.assertEqual(wrapper(None, None).body, 'Hello!')

    def test_add_route_with_view_permission(self):
        from repoze.bfg.interfaces import IAuthenticationPolicy
        from repoze.bfg.interfaces import IAuthorizationPolicy
        config = self._makeOne()
        policy = lambda *arg: None
        config.registry.registerUtility(policy, IAuthenticationPolicy)
        config.registry.registerUtility(policy, IAuthorizationPolicy)
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view, view_permission='edit')
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, None, request_type)
        route = self._assertRoute(config, 'name', 'path')
        self.failUnless(hasattr(wrapper, '__call_permissive__'))

    def test_add_route_with_view_permission_alias(self):
        from repoze.bfg.interfaces import IAuthenticationPolicy
        from repoze.bfg.interfaces import IAuthorizationPolicy
        config = self._makeOne()
        policy = lambda *arg: None
        config.registry.registerUtility(policy, IAuthenticationPolicy)
        config.registry.registerUtility(policy, IAuthorizationPolicy)
        view = lambda *arg: 'OK'
        config.add_route('name', 'path', view=view, permission='edit')
        request_type = self._getRouteRequestIface(config, 'name')
        wrapper = self._getViewCallable(config, None, request_type)
        route = self._assertRoute(config, 'name', 'path')
        self.failUnless(hasattr(wrapper, '__call_permissive__'))

    def test__override_not_yet_registered(self):
        from repoze.bfg.interfaces import IPackageOverrides
        package = DummyPackage('package')
        opackage = DummyPackage('opackage')
        config = self._makeOne()
        config._override(package, 'path', opackage, 'oprefix',
                         PackageOverrides=DummyOverrides)
        overrides = config.registry.queryUtility(IPackageOverrides,
                                                 name='package')
        self.assertEqual(overrides.inserted, [('path', 'opackage', 'oprefix')])
        self.assertEqual(overrides.package, package)

    def test__override_already_registered(self):
        from repoze.bfg.interfaces import IPackageOverrides
        package = DummyPackage('package')
        opackage = DummyPackage('opackage')
        overrides = DummyOverrides(package)
        config = self._makeOne()
        config.registry.registerUtility(overrides, IPackageOverrides,
                                        name='package')
        config._override(package, 'path', opackage, 'oprefix',
                         PackageOverrides=DummyOverrides)
        self.assertEqual(overrides.inserted, [('path', 'opackage', 'oprefix')])
        self.assertEqual(overrides.package, package)

    def test_add_static_view_here_relative(self):
        from repoze.bfg.static import PackageURLParser
        from zope.interface import implementedBy
        from repoze.bfg.static import StaticRootFactory
        from repoze.bfg.interfaces import IView
        config = self._makeOne()
        config.add_static_view('static', 'fixtures/static')
        request_type = self._getRouteRequestIface(config, 'static')
        route = self._assertRoute(config, 'static', 'static*subpath')
        self.assertEqual(route.factory.__class__, StaticRootFactory)
        iface = implementedBy(StaticRootFactory)
        wrapped = config.registry.adapters.lookup(
            (iface, request_type), IView, name='')
        request = self._makeRequest(config)
        self.assertEqual(wrapped(None, request).__class__, PackageURLParser)

    def test_add_static_view_package_relative(self):
        from repoze.bfg.static import PackageURLParser
        from zope.interface import implementedBy
        from repoze.bfg.static import StaticRootFactory
        from repoze.bfg.interfaces import IView
        config = self._makeOne()
        config.add_static_view('static', 'repoze.bfg.tests:fixtures/static')
        request_type = self._getRouteRequestIface(config, 'static')
        route = self._assertRoute(config, 'static', 'static*subpath')
        self.assertEqual(route.factory.__class__, StaticRootFactory)
        iface = implementedBy(StaticRootFactory)
        wrapped = config.registry.adapters.lookup(
            (iface, request_type), IView, name='')
        request = self._makeRequest(config)
        self.assertEqual(wrapped(None, request).__class__, PackageURLParser)

    def test_add_static_view_absolute(self):
        from paste.urlparser import StaticURLParser
        import os
        from zope.interface import implementedBy
        from repoze.bfg.static import StaticRootFactory
        from repoze.bfg.interfaces import IView
        config = self._makeOne()
        here = os.path.dirname(__file__)
        static_path = os.path.join(here, 'fixtures', 'static')
        config.add_static_view('static', static_path)
        request_type = self._getRouteRequestIface(config, 'static')
        route = self._assertRoute(config, 'static', 'static*subpath')
        self.assertEqual(route.factory.__class__, StaticRootFactory)
        iface = implementedBy(StaticRootFactory)
        wrapped = config.registry.adapters.lookup(
            (iface, request_type), IView, name='')
        request = self._makeRequest(config)
        self.assertEqual(wrapped(None, request).__class__, StaticURLParser)

    def test__system_view_no_view_no_renderer(self):
        from zope.configuration.exceptions import ConfigurationError
        config = self._makeOne()
        self.assertRaises(ConfigurationError, config._system_view, IDummy)

    def test__system_view_no_view_with_renderer(self):
        config = self._makeOne()
        self._registerRenderer(config, name='.pt')
        config._system_view(IDummy,
                           renderer='repoze.bfg.tests:fixtures/minimal.pt')
        request = self._makeRequest(config)
        view = config.registry.getUtility(IDummy)
        result = view(None, request)
        self.assertEqual(result.body, 'Hello!')

    def test__system_view_with_attr(self):
        config = self._makeOne()
        class view(object):
            def __init__(self, context, request):
                pass
            def index(self):
                return 'OK'
        config._system_view(IDummy, view=view, attr='index')
        view = config.registry.getUtility(IDummy)
        request = self._makeRequest(config)
        result = view(None, request)
        self.assertEqual(result, 'OK')

    def test__system_view_with_wrapper(self):
        from zope.interface import Interface
        from zope.interface import directlyProvides
        from repoze.bfg.interfaces import IRequest
        from repoze.bfg.interfaces import IView
        config = self._makeOne()
        view = lambda *arg: DummyResponse()
        wrapper = lambda *arg: 'OK2'
        config.registry.registerAdapter(wrapper, (Interface, Interface),
                                        IView, name='wrapper')
        config._system_view(IDummy, view=view, wrapper='wrapper')
        view = config.registry.getUtility(IDummy)
        request = self._makeRequest(config)
        directlyProvides(request, IRequest)
        request.registry = config.registry
        context = DummyContext()
        result = view(context, request)
        self.assertEqual(result, 'OK2')

    def test_set_notfound_view(self):
        from repoze.bfg.interfaces import INotFoundView
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.set_notfound_view(view)
        request = self._makeRequest(config)
        view = config.registry.getUtility(INotFoundView)
        result = view(None, request)
        self.assertEqual(result, 'OK')

    def test_set_forbidden_view(self):
        from repoze.bfg.interfaces import IForbiddenView
        config = self._makeOne()
        view = lambda *arg: 'OK'
        config.set_forbidden_view(view)
        request = self._makeRequest(config)
        view = config.registry.getUtility(IForbiddenView)
        result = view(None, request)
        self.assertEqual(result, 'OK')

    def test__set_authentication_policy(self):
        from repoze.bfg.interfaces import IAuthenticationPolicy
        config = self._makeOne()
        policy = object()
        config._set_authentication_policy(policy)
        self.assertEqual(
            config.registry.getUtility(IAuthenticationPolicy), policy)

    def test__set_authorization_policy(self):
        from repoze.bfg.interfaces import IAuthorizationPolicy
        config = self._makeOne()
        policy = object()
        config._set_authorization_policy(policy)
        self.assertEqual(
            config.registry.getUtility(IAuthorizationPolicy), policy)

    def test__derive_view_as_function_context_and_request(self):
        def view(context, request):
            return 'OK'
        config = self._makeOne()
        result = config._derive_view(view)
        self.failUnless(result is view)
        self.failIf(hasattr(result, '__call_permissive__'))
        self.assertEqual(view(None, None), 'OK')
        
    def test__derive_view_as_function_requestonly(self):
        def view(request):
            return 'OK'
        config = self._makeOne()
        result = config._derive_view(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.failIf(hasattr(result, '__call_permissive__'))
        self.assertEqual(result(None, None), 'OK')

    def test__derive_view_as_newstyle_class_context_and_request(self):
        class view(object):
            def __init__(self, context, request):
                pass
            def __call__(self):
                return 'OK'
        config = self._makeOne()
        result = config._derive_view(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.failIf(hasattr(result, '__call_permissive__'))
        self.assertEqual(result(None, None), 'OK')
        
    def test__derive_view_as_newstyle_class_requestonly(self):
        class view(object):
            def __init__(self, context, request):
                pass
            def __call__(self):
                return 'OK'
        config = self._makeOne()
        result = config._derive_view(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.failIf(hasattr(result, '__call_permissive__'))
        self.assertEqual(result(None, None), 'OK')

    def test__derive_view_as_oldstyle_class_context_and_request(self):
        class view:
            def __init__(self, context, request):
                pass
            def __call__(self):
                return 'OK'
        config = self._makeOne()
        result = config._derive_view(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.failIf(hasattr(result, '__call_permissive__'))
        self.assertEqual(result(None, None), 'OK')
        
    def test__derive_view_as_oldstyle_class_requestonly(self):
        class view:
            def __init__(self, context, request):
                pass
            def __call__(self):
                return 'OK'
        config = self._makeOne()
        result = config._derive_view(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.failIf(hasattr(result, '__call_permissive__'))
        self.assertEqual(result(None, None), 'OK')

    def test__derive_view_as_instance_context_and_request(self):
        class View:
            def __call__(self, context, request):
                return 'OK'
        view = View()
        config = self._makeOne()
        result = config._derive_view(view)
        self.failUnless(result is view)
        self.failIf(hasattr(result, '__call_permissive__'))
        self.assertEqual(result(None, None), 'OK')
        
    def test__derive_view_as_instance_requestonly(self):
        class View:
            def __call__(self, request):
                return 'OK'
        view = View()
        config = self._makeOne()
        result = config._derive_view(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.failUnless('instance' in result.__name__)
        self.failIf(hasattr(result, '__call_permissive__'))
        self.assertEqual(result(None, None), 'OK')

    def test__derive_view_with_debug_authorization_no_authpol(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        self._registerSettings(config,
                               debug_authorization=True, reload_templates=True)
        logger = self._registerLogger(config)
        result = config._derive_view(view, permission='view')
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.failIf(hasattr(result, '__call_permissive__'))
        request = self._makeRequest(config)
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertEqual(result(None, request), 'OK')
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url url (view name "
                         "'view_name' against context None): Allowed "
                         "(no authorization policy in use)")

    def test__derive_view_with_debug_authorization_no_permission(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        self._registerSettings(config,
                               debug_authorization=True, reload_templates=True)
        self._registerSecurityPolicy(config, True)
        logger = self._registerLogger(config)
        result = config._derive_view(view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.failIf(hasattr(result, '__call_permissive__'))
        request = self._makeRequest(config)
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertEqual(result(None, request), 'OK')
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url url (view name "
                         "'view_name' against context None): Allowed ("
                         "no permission registered)")

    def test__derive_view_debug_auth_permission_authpol_permitted(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        self._registerSettings(config, debug_authorization=True,
                               reload_templates=True)
        logger = self._registerLogger(config)
        self._registerSecurityPolicy(config, True)
        result = config._derive_view(view, permission='view')
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result.__call_permissive__, view)
        request = self._makeRequest(config)
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertEqual(result(None, request), 'OK')
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url url (view name "
                         "'view_name' against context None): True")
        
    def test__derive_view_debug_auth_permission_authpol_denied(self):
        from repoze.bfg.exceptions import Forbidden
        view = lambda *arg: 'OK'
        config = self._makeOne()
        self._registerSettings(config,
                               debug_authorization=True, reload_templates=True)
        logger = self._registerLogger(config)
        self._registerSecurityPolicy(config, False)
        result = config._derive_view(view, permission='view')
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result.__call_permissive__, view)
        request = self._makeRequest(config)
        request.view_name = 'view_name'
        request.url = 'url'
        self.assertRaises(Forbidden, result, None, request)
        self.assertEqual(len(logger.messages), 1)
        self.assertEqual(logger.messages[0],
                         "debug_authorization of url url (view name "
                         "'view_name' against context None): False")

    def test__derive_view_debug_auth_permission_authpol_denied2(self):
        view = lambda *arg: 'OK'
        config = self._makeOne()
        self._registerSettings(config,
                               debug_authorization=True, reload_templates=True)
        logger = self._registerLogger(config)
        self._registerSecurityPolicy(config, False)
        result = config._derive_view(view, permission='view')
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        request = self._makeRequest(config)
        request.view_name = 'view_name'
        request.url = 'url'
        permitted = result.__permitted__(None, None)
        self.assertEqual(permitted, False)

    def test__derive_view_with_predicates_all(self):
        view = lambda *arg: 'OK'
        predicates = []
        def predicate1(context, request):
            predicates.append(True)
            return True
        def predicate2(context, request):
            predicates.append(True)
            return True
        config = self._makeOne()
        result = config._derive_view(view, predicates=[predicate1, predicate2])
        request = self._makeRequest(config)
        request.method = 'POST'
        next = result(None, None)
        self.assertEqual(next, 'OK')
        self.assertEqual(predicates, [True, True])

    def test__derive_view_with_predicates_checker(self):
        view = lambda *arg: 'OK'
        predicates = []
        def predicate1(context, request):
            predicates.append(True)
            return True
        def predicate2(context, request):
            predicates.append(True)
            return True
        config = self._makeOne()
        result = config._derive_view(view, predicates=[predicate1, predicate2])
        request = self._makeRequest(config)
        request.method = 'POST'
        next = result.__predicated__(None, None)
        self.assertEqual(next, True)
        self.assertEqual(predicates, [True, True])

    def test__derive_view_with_predicates_notall(self):
        from repoze.bfg.exceptions import NotFound
        view = lambda *arg: 'OK'
        predicates = []
        def predicate1(context, request):
            predicates.append(True)
            return True
        def predicate2(context, request):
            predicates.append(True)
            return False
        config = self._makeOne()
        result = config._derive_view(view, predicates=[predicate1, predicate2])
        request = self._makeRequest(config)
        request.method = 'POST'
        self.assertRaises(NotFound, result, None, None)
        self.assertEqual(predicates, [True, True])

    def test__derive_view_with_wrapper_viewname(self):
        from webob import Response
        from repoze.bfg.interfaces import IView
        inner_response = Response('OK')
        def inner_view(context, request):
            return inner_response
        def outer_view(context, request):
            self.assertEqual(request.wrapped_response, inner_response)
            self.assertEqual(request.wrapped_body, inner_response.body)
            self.assertEqual(request.wrapped_view, inner_view)
            return Response('outer ' + request.wrapped_body)
        config = self._makeOne()
        config.registry.registerAdapter(
            outer_view, (None, None), IView, 'owrap')
        result = config._derive_view(inner_view, viewname='inner',
                                    wrapper_viewname='owrap')
        self.failIf(result is inner_view)
        self.assertEqual(inner_view.__module__, result.__module__)
        self.assertEqual(inner_view.__doc__, result.__doc__)
        request = self._makeRequest(config)
        request.registry = config.registry
        response = result(None, request)
        self.assertEqual(response.body, 'outer OK')

    def test__derive_view_with_wrapper_viewname_notfound(self):
        from webob import Response
        inner_response = Response('OK')
        def inner_view(context, request):
            return inner_response
        config = self._makeOne()
        request = self._makeRequest(config)
        request.registry = config.registry
        wrapped = config._derive_view(
            inner_view, viewname='inner', wrapper_viewname='owrap')
        result = self.assertRaises(ValueError, wrapped, None, request)

    def test_override_resource_samename(self):
        from zope.configuration.exceptions import ConfigurationError
        config = self._makeOne()
        self.assertRaises(ConfigurationError, config.override_resource,'a', 'a')

    def test_override_resource_directory_with_file(self):
        from zope.configuration.exceptions import ConfigurationError
        config = self._makeOne()
        self.assertRaises(ConfigurationError, config.override_resource,
                          'a:foo/', 'a:foo.pt')

    def test_override_resource_file_with_directory(self):
        from zope.configuration.exceptions import ConfigurationError
        config = self._makeOne()
        self.assertRaises(ConfigurationError, config.override_resource,
                          'a:foo.pt', 'a:foo/')

    def test_override_resource_success(self):
        config = self._makeOne()
        override = DummyUnderOverride()
        config.override_resource(
            'repoze.bfg.tests.fixtureapp:templates/foo.pt',
            'repoze.bfg.tests.fixtureapp.subpackage:templates/bar.pt',
            _override=override)
        from repoze.bfg.tests import fixtureapp
        from repoze.bfg.tests.fixtureapp import subpackage
        self.assertEqual(override.package, fixtureapp)
        self.assertEqual(override.path, 'templates/foo.pt')
        self.assertEqual(override.override_package, subpackage)
        self.assertEqual(override.override_prefix, 'templates/bar.pt')

    def test_add_renderer(self):
        from repoze.bfg.interfaces import IRendererFactory
        config = self._makeOne()
        renderer = object()
        config.add_renderer('name', renderer)
        self.assertEqual(config.registry.getUtility(IRendererFactory, 'name'),
                         renderer)

    def test_scan_integration(self):
        from zope.interface import alsoProvides
        from repoze.bfg.interfaces import IRequest
        from repoze.bfg.view import render_view_to_response
        import repoze.bfg.tests.grokkedapp as package
        config = self._makeOne()
        config.scan(package)

        ctx = DummyContext()
        req = DummyRequest()
        alsoProvides(req, IRequest)
        req.registry = config.registry

        req.method = 'GET'
        result = render_view_to_response(ctx, req, '')
        self.assertEqual(result, 'grokked')

        req.method = 'POST'
        result = render_view_to_response(ctx, req, '')
        self.assertEqual(result, 'grokked_post')

        result= render_view_to_response(ctx, req, 'grokked_class')
        self.assertEqual(result, 'grokked_class')

        result= render_view_to_response(ctx, req, 'grokked_instance')
        self.assertEqual(result, 'grokked_instance')

        result= render_view_to_response(ctx, req, 'oldstyle_grokked_class')
        self.assertEqual(result, 'oldstyle_grokked_class')

        req.method = 'GET'
        result = render_view_to_response(ctx, req, 'another')
        self.assertEqual(result, 'another_grokked')

        req.method = 'POST'
        result = render_view_to_response(ctx, req, 'another')
        self.assertEqual(result, 'another_grokked_post')

        result= render_view_to_response(ctx, req, 'another_grokked_class')
        self.assertEqual(result, 'another_grokked_class')

        result= render_view_to_response(ctx, req, 'another_grokked_instance')
        self.assertEqual(result, 'another_grokked_instance')

        result= render_view_to_response(ctx, req,
                                        'another_oldstyle_grokked_class')
        self.assertEqual(result, 'another_oldstyle_grokked_class')

        result = render_view_to_response(ctx, req, 'stacked1')
        self.assertEqual(result, 'stacked')

        result = render_view_to_response(ctx, req, 'stacked2')
        self.assertEqual(result, 'stacked')

        result = render_view_to_response(ctx, req, 'another_stacked1')
        self.assertEqual(result, 'another_stacked')

        result = render_view_to_response(ctx, req, 'another_stacked2')
        self.assertEqual(result, 'another_stacked')

        result = render_view_to_response(ctx, req, 'stacked_class1')
        self.assertEqual(result, 'stacked_class')

        result = render_view_to_response(ctx, req, 'stacked_class2')
        self.assertEqual(result, 'stacked_class')

        result = render_view_to_response(ctx, req, 'another_stacked_class1')
        self.assertEqual(result, 'another_stacked_class')

        result = render_view_to_response(ctx, req, 'another_stacked_class2')
        self.assertEqual(result, 'another_stacked_class')

        self.assertRaises(TypeError,
                          render_view_to_response, ctx, req, 'basemethod')

        result = render_view_to_response(ctx, req, 'method1')
        self.assertEqual(result, 'method1')

        result = render_view_to_response(ctx, req, 'method2')
        self.assertEqual(result, 'method2')

        result = render_view_to_response(ctx, req, 'stacked_method1')
        self.assertEqual(result, 'stacked_method')

        result = render_view_to_response(ctx, req, 'stacked_method2')
        self.assertEqual(result, 'stacked_method')
        
        result = render_view_to_response(ctx, req, 'subpackage_init')
        self.assertEqual(result, 'subpackage_init')
        
        result = render_view_to_response(ctx, req, 'subpackage_notinit')
        self.assertEqual(result, 'subpackage_notinit')

        result = render_view_to_response(ctx, req, 'subsubpackage_init')
        self.assertEqual(result, 'subsubpackage_init')

        result = render_view_to_response(ctx, req, 'pod_notinit')
        self.assertEqual(result, None)

class Test__map_view(unittest.TestCase):
    def setUp(self):
        from repoze.bfg.registry import Registry
        self.registry = Registry()

    def tearDown(self):
        del self.registry
        
    def _registerRenderer(self, name='.txt'):
        from repoze.bfg.interfaces import IRendererFactory
        from repoze.bfg.interfaces import ITemplateRenderer
        from zope.interface import implements
        class Renderer:
            implements(ITemplateRenderer)
            def __init__(self, path):
                self.__class__.path = path
            def __call__(self, *arg):
                return 'Hello!'
        self.registry.registerUtility(Renderer, IRendererFactory, name=name)
        return Renderer(name)

    def _makeRequest(self):
        request = DummyRequest()
        request.registry = self.registry
        return request

    def _callFUT(self, *arg, **kw):
        from repoze.bfg.configuration import _map_view
        return _map_view(*arg, **kw)
    
    def test__map_view_as_function_context_and_request(self):
        def view(context, request):
            return 'OK'
        result = self._callFUT(view)
        self.failUnless(result is view)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_function_with_attr(self):
        def view(context, request):
            """ """
        result = self._callFUT(view, attr='__name__')
        self.failIf(result is view)
        self.assertRaises(TypeError, result, None, None)

    def test__map_view_as_function_with_attr_and_renderer(self):
        renderer = self._registerRenderer()
        view = lambda *arg: 'OK'
        result = self._callFUT(view, attr='__name__', renderer=renderer)
        self.failIf(result is view)
        self.assertRaises(TypeError, result, None, None)
        
    def test__map_view_as_function_requestonly(self):
        def view(request):
            return 'OK'
        result = self._callFUT(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_function_requestonly_with_attr(self):
        def view(request):
            """ """
        result = self._callFUT(view, attr='__name__')
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertRaises(TypeError, result, None, None)

    def test__map_view_as_newstyle_class_context_and_request(self):
        class view(object):
            def __init__(self, context, request):
                pass
            def __call__(self):
                return 'OK'
        result = self._callFUT(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_newstyle_class_context_and_request_with_attr(self):
        class view(object):
            def __init__(self, context, request):
                pass
            def index(self):
                return 'OK'
        result = self._callFUT(view, attr='index')
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_newstyle_class_context_and_request_attr_and_renderer(
        self):
        renderer = self._registerRenderer()
        class view(object):
            def __init__(self, context, request):
                pass
            def index(self):
                return {'a':'1'}
        result = self._callFUT(view, attr='index', renderer = renderer)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        request = self._makeRequest()
        self.assertEqual(result(None, request).body, 'Hello!')
        
    def test__map_view_as_newstyle_class_requestonly(self):
        class view(object):
            def __init__(self, request):
                pass
            def __call__(self):
                return 'OK'
        result = self._callFUT(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_newstyle_class_requestonly_with_attr(self):
        class view(object):
            def __init__(self, request):
                pass
            def index(self):
                return 'OK'
        result = self._callFUT(view, attr='index')
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_newstyle_class_requestonly_attr_and_renderer(self):
        renderer = self._registerRenderer()
        class view(object):
            def __init__(self, request):
                pass
            def index(self):
                return {'a':'1'}
        result = self._callFUT(view, attr='index', renderer = renderer)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        request = self._makeRequest()
        self.assertEqual(result(None, request).body, 'Hello!')

    def test__map_view_as_oldstyle_class_context_and_request(self):
        class view:
            def __init__(self, context, request):
                pass
            def __call__(self):
                return 'OK'
        result = self._callFUT(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_oldstyle_class_context_and_request_with_attr(self):
        class view:
            def __init__(self, context, request):
                pass
            def index(self):
                return 'OK'
        result = self._callFUT(view, attr='index')
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_oldstyle_cls_context_request_attr_and_renderer(self):
        renderer = self._registerRenderer()
        class view:
            def __init__(self, context, request):
                pass
            def index(self):
                return {'a':'1'}
        result = self._callFUT(view, attr='index', renderer = renderer)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        request = self._makeRequest()
        self.assertEqual(result(None, request).body, 'Hello!')

    def test__map_view_as_oldstyle_class_requestonly(self):
        class view:
            def __init__(self, request):
                pass
            def __call__(self):
                return 'OK'
        result = self._callFUT(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_oldstyle_class_requestonly_with_attr(self):
        class view:
            def __init__(self, request):
                pass
            def index(self):
                return 'OK'
        result = self._callFUT(view, attr='index')
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_oldstyle_class_requestonly_attr_and_renderer(self):
        renderer = self._registerRenderer()
        class view:
            def __init__(self, request):
                pass
            def index(self):
                return {'a':'1'}
        result = self._callFUT(view, attr='index', renderer = renderer)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.assertEqual(view.__name__, result.__name__)
        request = self._makeRequest()
        self.assertEqual(result(None, request).body, 'Hello!')

    def test__map_view_as_instance_context_and_request(self):
        class View:
            def __call__(self, context, request):
                return 'OK'
        view = View()
        result = self._callFUT(view)
        self.failUnless(result is view)
        self.assertEqual(result(None, None), 'OK')
        
    def test__map_view_as_instance_context_and_request_and_attr(self):
        class View:
            def index(self, context, request):
                return 'OK'
        view = View()
        result = self._callFUT(view, attr='index')
        self.failIf(result is view)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_instance_context_and_request_attr_and_renderer(self):
        renderer = self._registerRenderer()
        class View:
            def index(self, context, request):
                return {'a':'1'}
        view = View()
        result = self._callFUT(view, attr='index', renderer=renderer)
        self.failIf(result is view)
        request = self._makeRequest()
        self.assertEqual(result(None, request).body, 'Hello!')

    def test__map_view_as_instance_requestonly(self):
        class View:
            def __call__(self, request):
                return 'OK'
        view = View()
        result = self._callFUT(view)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.failUnless('instance' in result.__name__)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_instance_requestonly_with_attr(self):
        class View:
            def index(self, request):
                return 'OK'
        view = View()
        result = self._callFUT(view, attr='index')
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.failUnless('instance' in result.__name__)
        self.assertEqual(result(None, None), 'OK')

    def test__map_view_as_instance_requestonly_with_attr_and_renderer(self):
        renderer = self._registerRenderer()
        class View:
            def index(self, request):
                return {'a':'1'}
        view = View()
        result = self._callFUT(view, attr='index', renderer = renderer)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        self.failUnless('instance' in result.__name__)
        request = self._makeRequest()
        self.assertEqual(result(None, request).body, 'Hello!')

    def test__map_view_rendereronly(self):
        renderer = self._registerRenderer()
        def view(context, request):
            return {'a':'1'}
        result = self._callFUT(view, renderer=renderer)
        self.failIf(result is view)
        self.assertEqual(view.__module__, result.__module__)
        self.assertEqual(view.__doc__, result.__doc__)
        request = self._makeRequest()
        self.assertEqual(result(None, request).body, 'Hello!')

class Test_rendered_response(unittest.TestCase):
    def setUp(self):
        testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _callFUT(self, renderer, response, view=None,
                 context=None, request=None, renderer_name=None):
        from repoze.bfg.configuration import rendered_response
        if request is None:
            request = DummyRequest()
        return rendered_response(renderer, response, view,
                                 context, request, renderer_name)

    def _makeRenderer(self):
        def renderer(*arg):
            return 'Hello!'
        return renderer

    def test_is_response(self):
        renderer = self._makeRenderer()
        response = DummyResponse()
        result = self._callFUT(renderer, response)
        self.assertEqual(result, response)

    def test_calls_renderer(self):
        renderer = self._makeRenderer()
        response = {'a':'1'}
        result = self._callFUT(renderer, response)
        self.assertEqual(result.body, 'Hello!')

    def test_with_content_type(self):
        renderer = self._makeRenderer()
        response = {'a':'1'}
        request = DummyRequest()
        attrs = {'response_content_type':'text/nonsense'}
        request.__dict__.update(attrs)
        result = self._callFUT(renderer, response, request=request)
        self.assertEqual(result.content_type, 'text/nonsense')

    def test_with_headerlist(self):
        renderer = self._makeRenderer()
        response = {'a':'1'}
        request = DummyRequest()
        attrs = {'response_headerlist':[('a', '1'), ('b', '2')]}
        request.__dict__.update(attrs)
        result = self._callFUT(renderer, response, request=request)
        self.assertEqual(result.headerlist,
                         [('Content-Type', 'text/html; charset=UTF-8'),
                          ('Content-Length', '6'),
                          ('a', '1'),
                          ('b', '2')])

    def test_with_status(self):
        renderer = self._makeRenderer()
        response = {'a':'1'}
        request = DummyRequest()
        attrs = {'response_status':'406 You Lose'}
        request.__dict__.update(attrs)
        result = self._callFUT(renderer, response, request=request)
        self.assertEqual(result.status, '406 You Lose')

    def test_with_charset(self):
        renderer = self._makeRenderer()
        response = {'a':'1'}
        request = DummyRequest()
        attrs = {'response_charset':'UTF-16'}
        request.__dict__.update(attrs)
        result = self._callFUT(renderer, response, request=request)
        self.assertEqual(result.charset, 'UTF-16')

    def test_with_cache_for(self):
        renderer = self._makeRenderer()
        response = {'a':'1'}
        request = DummyRequest()
        attrs = {'response_cache_for':100}
        request.__dict__.update(attrs)
        result = self._callFUT(renderer, response, request=request)
        self.assertEqual(result.cache_control.max_age, 100)

class Test_decorate_view(unittest.TestCase):
    def _callFUT(self, wrapped, original):
        from repoze.bfg.configuration import decorate_view
        return decorate_view(wrapped, original)
    
    def test_it_same(self):
        def view(context, request):
            """ """
        result = self._callFUT(view, view)
        self.assertEqual(result, False)

    def test_it_different(self):
        class DummyView1:
            """ 1 """
            __name__ = '1'
            __module__ = '1'
            def __call__(self, context, request):
                """ """
            def __call_permissive__(self, context, reuqest):
                """ """
            def __predicated__(self, context, reuqest):
                """ """
            def __permitted__(self, context, request):
                """ """
        class DummyView2:
            """ 2 """
            __name__ = '2'
            __module__ = '2'
            def __call__(self, context, request):
                """ """
            def __call_permissive__(self, context, reuqest):
                """ """
            def __predicated__(self, context, reuqest):
                """ """
            def __permitted__(self, context, request):
                """ """
        view1 = DummyView1()
        view2 = DummyView2()
        result = self._callFUT(view1, view2)
        self.assertEqual(result, True)
        self.failUnless(view1.__doc__ is view2.__doc__)
        self.failUnless(view1.__module__ is view2.__module__)
        self.failUnless(view1.__name__ is view2.__name__)
        self.failUnless(view1.__call_permissive__.im_func is
                        view2.__call_permissive__.im_func)
        self.failUnless(view1.__permitted__.im_func is
                        view2.__permitted__.im_func)
        self.failUnless(view1.__predicated__.im_func is
                        view2.__predicated__.im_func)


class TestMultiView(unittest.TestCase):
    def _getTargetClass(self):
        from repoze.bfg.configuration import MultiView
        return MultiView

    def _makeOne(self, name='name'):
        return self._getTargetClass()(name)
    
    def test_class_implements_ISecuredView(self):
        from zope.interface.verify import verifyClass
        from repoze.bfg.interfaces import ISecuredView
        verifyClass(ISecuredView, self._getTargetClass())

    def test_instance_implements_ISecuredView(self):
        from zope.interface.verify import verifyObject
        from repoze.bfg.interfaces import ISecuredView
        verifyObject(ISecuredView, self._makeOne())

    def test_add(self):
        mv = self._makeOne()
        mv.add('view', 100)
        self.assertEqual(mv.views, [(100, 'view')])
        mv.add('view2', 99)
        self.assertEqual(mv.views, [(99, 'view2'), (100, 'view')])

    def test_match_not_found(self):
        from repoze.bfg.exceptions import NotFound
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        self.assertRaises(NotFound, mv.match, context, request)

    def test_match_predicate_fails(self):
        from repoze.bfg.exceptions import NotFound
        mv = self._makeOne()
        def view(context, request):
            """ """
        view.__predicated__ = lambda *arg: False
        mv.views = [(100, view)]
        context = DummyContext()
        request = DummyRequest()
        self.assertRaises(NotFound, mv.match, context, request)

    def test_match_predicate_succeeds(self):
        mv = self._makeOne()
        def view(context, request):
            """ """
        view.__predicated__ = lambda *arg: True
        mv.views = [(100, view)]
        context = DummyContext()
        request = DummyRequest()
        result = mv.match(context, request)
        self.assertEqual(result, view)

    def test_permitted_no_views(self):
        from repoze.bfg.exceptions import NotFound
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        self.assertRaises(NotFound, mv.__permitted__, context, request)

    def test_permitted_no_match_with__permitted__(self):
        mv = self._makeOne()
        def view(context, request):
            """ """
        mv.views = [(100, view)]
        context = DummyContext()
        request = DummyRequest()
        self.assertEqual(mv.__permitted__(None, None), True)
        
    def test_permitted(self):
        mv = self._makeOne()
        def view(context, request):
            """ """
        def permitted(context, request):
            return False
        view.__permitted__ = permitted
        mv.views = [(100, view)]
        context = DummyContext()
        request = DummyRequest()
        result = mv.__permitted__(context, request)
        self.assertEqual(result, False)

    def test__call__not_found(self):
        from repoze.bfg.exceptions import NotFound
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        self.assertRaises(NotFound, mv, context, request)

    def test___call__intermediate_not_found(self):
        from repoze.bfg.exceptions import NotFound
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        request.view_name = ''
        expected_response = DummyResponse()
        def view1(context, request):
            raise NotFound
        def view2(context, request):
            return expected_response
        mv.views = [(100, view1), (99, view2)]
        response = mv(context, request)
        self.assertEqual(response, expected_response)

    def test___call__(self):
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        request.view_name = ''
        expected_response = DummyResponse()
        def view(context, request):
            return expected_response
        mv.views = [(100, view)]
        response = mv(context, request)
        self.assertEqual(response, expected_response)

    def test__call_permissive__not_found(self):
        from repoze.bfg.exceptions import NotFound
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        self.assertRaises(NotFound, mv, context, request)

    def test___call_permissive_has_call_permissive(self):
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        request.view_name = ''
        expected_response = DummyResponse()
        def view(context, request):
            """ """
        def permissive(context, request):
            return expected_response
        view.__call_permissive__ = permissive
        mv.views = [(100, view)]
        response = mv.__call_permissive__(context, request)
        self.assertEqual(response, expected_response)

    def test___call_permissive_has_no_call_permissive(self):
        mv = self._makeOne()
        context = DummyContext()
        request = DummyRequest()
        request.view_name = ''
        expected_response = DummyResponse()
        def view(context, request):
            return expected_response
        mv.views = [(100, view)]
        response = mv.__call_permissive__(context, request)
        self.assertEqual(response, expected_response)

class TestRequestOnly(unittest.TestCase):
    def _callFUT(self, arg):
        from repoze.bfg.configuration import requestonly
        return requestonly(arg)
    
    def test_newstyle_class_no_init(self):
        class foo(object):
            """ """
        self.assertFalse(self._callFUT(foo))

    def test_newstyle_class_init_toomanyargs(self):
        class foo(object):
            def __init__(self, context, request):
                """ """
        self.assertFalse(self._callFUT(foo))
        
    def test_newstyle_class_init_onearg_named_request(self):
        class foo(object):
            def __init__(self, request):
                """ """
        self.assertTrue(self._callFUT(foo))

    def test_newstyle_class_init_onearg_named_somethingelse(self):
        class foo(object):
            def __init__(self, req):
                """ """
        self.assertTrue(self._callFUT(foo))

    def test_newstyle_class_init_defaultargs_firstname_not_request(self):
        class foo(object):
            def __init__(self, context, request=None):
                """ """
        self.assertFalse(self._callFUT(foo))

    def test_newstyle_class_init_defaultargs_firstname_request(self):
        class foo(object):
            def __init__(self, request, foo=1, bar=2):
                """ """
        self.assertTrue(self._callFUT(foo))

    def test_newstyle_class_init_noargs(self):
        class foo(object):
            def __init__():
                """ """
        self.assertFalse(self._callFUT(foo))

    def test_oldstyle_class_no_init(self):
        class foo:
            """ """
        self.assertFalse(self._callFUT(foo))

    def test_oldstyle_class_init_toomanyargs(self):
        class foo:
            def __init__(self, context, request):
                """ """
        self.assertFalse(self._callFUT(foo))
        
    def test_oldstyle_class_init_onearg_named_request(self):
        class foo:
            def __init__(self, request):
                """ """
        self.assertTrue(self._callFUT(foo))

    def test_oldstyle_class_init_onearg_named_somethingelse(self):
        class foo:
            def __init__(self, req):
                """ """
        self.assertTrue(self._callFUT(foo))

    def test_oldstyle_class_init_defaultargs_firstname_not_request(self):
        class foo:
            def __init__(self, context, request=None):
                """ """
        self.assertFalse(self._callFUT(foo))

    def test_oldstyle_class_init_defaultargs_firstname_request(self):
        class foo:
            def __init__(self, request, foo=1, bar=2):
                """ """
        self.assertTrue(self._callFUT(foo), True)

    def test_oldstyle_class_init_noargs(self):
        class foo:
            def __init__():
                """ """
        self.assertFalse(self._callFUT(foo))

    def test_function_toomanyargs(self):
        def foo(context, request):
            """ """
        self.assertFalse(self._callFUT(foo))
        
    def test_function_onearg_named_request(self):
        def foo(request):
            """ """
        self.assertTrue(self._callFUT(foo))

    def test_function_onearg_named_somethingelse(self):
        def foo(req):
            """ """
        self.assertTrue(self._callFUT(foo))

    def test_function_defaultargs_firstname_not_request(self):
        def foo(context, request=None):
            """ """
        self.assertFalse(self._callFUT(foo))

    def test_function_defaultargs_firstname_request(self):
        def foo(request, foo=1, bar=2):
            """ """
        self.assertTrue(self._callFUT(foo))

    def test_function_noargs(self):
        def foo():
            """ """
        self.assertFalse(self._callFUT(foo))

    def test_instance_toomanyargs(self):
        class Foo:
            def __call__(self, context, request):
                """ """
        foo = Foo()
        self.assertFalse(self._callFUT(foo))
        
    def test_instance_defaultargs_onearg_named_request(self):
        class Foo:
            def __call__(self, request):
                """ """
        foo = Foo()
        self.assertTrue(self._callFUT(foo))

    def test_instance_defaultargs_onearg_named_somethingelse(self):
        class Foo:
            def __call__(self, req):
                """ """
        foo = Foo()
        self.assertTrue(self._callFUT(foo))

    def test_instance_defaultargs_firstname_not_request(self):
        class Foo:
            def __call__(self, context, request=None):
                """ """
        foo = Foo()
        self.assertFalse(self._callFUT(foo))

    def test_instance_defaultargs_firstname_request(self):
        class Foo:
            def __call__(self, request, foo=1, bar=2):
                """ """
        foo = Foo()
        self.assertTrue(self._callFUT(foo), True)

    def test_instance_nocall(self):
        class Foo: pass
        foo = Foo()
        self.assertFalse(self._callFUT(foo))

class TestMakeApp(unittest.TestCase):
    def setUp(self):
        testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _callFUT(self, *arg, **kw):
        from repoze.bfg.configuration import make_app
        return make_app(*arg, **kw)

    def test_it(self):
        settings = {'a':1}
        rootfactory = object()
        app = self._callFUT(rootfactory, settings=settings,
                            Configurator=DummyConfigurator)
        self.assertEqual(app.root_factory, rootfactory)
        self.assertEqual(app.settings, settings)
        self.assertEqual(app.zcml_file, 'configure.zcml')
        self.assertEqual(app.hook_zca, True)

    def test_it_options_means_settings(self):
        settings = {'a':1}
        rootfactory = object()
        app = self._callFUT(rootfactory, options=settings,
                            Configurator=DummyConfigurator)
        self.assertEqual(app.root_factory, rootfactory)
        self.assertEqual(app.settings, settings)
        self.assertEqual(app.zcml_file, 'configure.zcml')

    def test_it_with_package(self):
        package = object()
        rootfactory = object()
        app = self._callFUT(rootfactory, package=package,
                            Configurator=DummyConfigurator)
        self.assertEqual(app.package, package)

    def test_it_with_custom_configure_zcml(self):
        rootfactory = object()
        settings = {'configure_zcml':'2.zcml'}
        app = self._callFUT(rootfactory, filename='1.zcml', settings=settings,
                            Configurator=DummyConfigurator)
        self.assertEqual(app.zcml_file, '2.zcml')


class DummyRequest:
    subpath = ()
    def __init__(self):
        self.environ = {'PATH_INFO':'/static'}
    def copy(self):
        return self
    def get_response(self, app):
        return app

class DummyRootFactory:
    def __init__(self, root):
        self.root = root

class DummyContext:
    pass

class DummyLock:
    def acquire(self):
        self.acquired = True

    def release(self):
        self.released = True
        
class DummyPackage:
    def __init__(self, name):
        self.__name__ = name

class DummyOverrides:
    def __init__(self, package):
        self.package = package
        self.inserted = []

    def insert(self, path, package, prefix):
        self.inserted.append((path, package, prefix))

class DummyUnderOverride:
    def __call__(self, package, path, override_package, override_prefix,
                 _info=u''):
        self.package = package
        self.path = path
        self.override_package = override_package
        self.override_prefix = override_prefix

from zope.interface import Interface
class IDummy(Interface):
    pass

class IOther(Interface):
    pass

class DummyResponse:
    status = '200 OK'
    headerlist = ()
    app_iter = ()
    body = ''

class DummyLogger:
    def __init__(self):
        self.messages = []
    def info(self, msg):
        self.messages.append(msg)
    warn = info
    debug = info

class DummySecurityPolicy:
    def __init__(self, permitted=True):
        self.permitted = permitted

    def effective_principals(self, request):
        return []

    def permits(self, context, principals, permission):
        return self.permitted

class DummyConfigurator(object):
    def __init__(self, registry=None, package=None,
                 root_factory=None, zcml_file=None,
                 settings=None, hook_zca=False):
        self.root_factory = root_factory
        self.package = package
        self.zcml_file = zcml_file
        self.settings = settings
        self.hook_zca = hook_zca
    
    def make_wsgi_app(self):
        return self
    
class DummyGetSiteManager(object):
    def sethook(self, reg):
        self.hook = reg
