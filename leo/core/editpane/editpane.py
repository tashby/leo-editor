import imp
import os

import leo.core.leoGlobals as g
from leo.core.leoNodes import vnode
from leo.core.leoQt import QtCore, QtGui, QtWidgets, QtConst

if g.isPython3:
    from importlib import import_module

import leo.core.signal_manager as sig

def DBG(text):
    """DBG - temporary debugging function

    :param str text: text to print
    """
    print("LEP: %s" % text)

class LeoEditPane(QtWidgets.QWidget):
    """
    Leo node body editor / viewer
    """
    def __init__(self, c=None, p=None, mode='edit', show_head=True, show_control=False,
                 update=True, recurse=False, *args, **kwargs):
        """__init__ - bind to outline

        :param outline c: outline to bind to
        """
        DBG("__init__ LEP")
        super(LeoEditPane, self).__init__(*args, **kwargs)

        self.c = c
        p = p or self.c.p
        self.mode = mode

        self.gnx = p.gnx

        self.load_modules()

        self._build_layout(
            show_head=show_head,
            show_control=show_control,
            update=update,
            recurse=recurse,
        )

        self.track   = self.cb_track.isChecked()
        self.update  = self.cb_update.isChecked()
        self.recurse = self.cb_recurse.isChecked()
        self.goto    = self.cb_goto.isChecked()

        self.set_widget(lep_type='EDITOR')
        self.set_widget(lep_type='TEXT')

        self.set_mode(self.mode)

        self.handlers = [
            ('select1', self._before_select),
            ('select2', self._after_select),
            # ('bodykey2', self._after_body_key),
        ]
        self._register_handlers()

    def _add_checkbox(self, text, state_changed, tooltip, checked=True,
        enabled=True, button_label=True):
        """
        _add_checkbox - helper to add a checkbox

        :param str text: Text for label
        :param function state_changed: callback for state_changed signal
        :param bool checked: initially checked?
        :param bool enabled: initially enabled?
        :param bool button_label: label should be a button for single shot use
        :return: QCheckBox
        """
        cbox = QtWidgets.QCheckBox('' if button_label else text, self)
        self.control.layout().addWidget(cbox)
        btn = None
        if button_label:
            btn = QtWidgets.QPushButton(text, self)
            self.control.layout().addWidget(btn)
            def cb(checked, cbox=cbox, state_changed=state_changed):
                state_changed(cbox.isChecked(), one_shot=True)
            btn.clicked.connect(cb)
            btn.setToolTip(tooltip)
        cbox.setChecked(checked)
        cbox.setEnabled(enabled)
        cbox.stateChanged.connect(state_changed)
        cbox.setToolTip(tooltip)
        self.control.layout().addItem(QtWidgets.QSpacerItem(20, 0))
        return cbox

    def _add_frame(self):
        """_add_frame - add a widget with a layout as a hiding target"""
        w = QtWidgets.QWidget(self)
        self.layout().addWidget(w)
        w.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        w.setLayout(QtWidgets.QHBoxLayout())
        w.layout().setContentsMargins(0, 0, 0, 0)
        w.layout().setSpacing(0)
        return w

    def _after_body_key(self, v):
        """_after_body_key - after Leo selects another node

        FIXME: although class EditCommandsClass-->insert &
        delete...-->selfInsertCommand() implies that bodykey2 should fire
        after all keys, it doesn't seem to fire after \n, backspace, delete
        etc., so the viewer gets out of date for those keys. The simplest
        fix would be a new bodychanged2 hook.

        :param str tag: handler name ("bodykey2")
        :param dict keywords: c, p, etc.
        :return: None
        """

        if sig.is_locked(self):
            return

        p = self.c.vnode2position(v)

        DBG("after body key")

        if self.update:
            self.update_position(p)

        return None

    def _after_select(self, tag, keywords):
        """_after_select - after Leo selects another node

        :param str tag: handler name ("select2")
        :param dict keywords: c, new_p, old_p
        :return: None
        """

        c = keywords['c']
        if c != self.c:
            return None

        DBG("after select")

        if self.track:
            self.new_position(keywords['new_p'])

        return None

    def _before_select(self, tag, keywords):
        """_before_select - before Leo selects another node

        :param str tag: handler name ("select1")
        :param dict keywords: c, new_p, old_p
        :return: None
        """

        c = keywords['c']
        if c != self.c:
            return None

        # currently nothing to do here, focusOut in widget takes care
        # of any text updates

        # BUT keyboard driven position change might need some action here
        # BUT then again, textChanged in widget is probably sufficient

        DBG("before select")

        return None

    def _find_gnx_node(self, gnx):
        '''Return the first position having the given gnx.'''
        if self.c.p.gnx == gnx:
            return self.c.p
        for p in self.c.all_unique_positions():
            if p.v.gnx == gnx:
                return p
        g.es("Edit/View pane couldn't find node")
        return None

    def _register_handlers(self):
        """_register_handlers - attach to Leo signals
        """
        DBG("\nregister handlers")
        for hook, handler in self.handlers:
            g.registerHandler(hook, handler)

        sig.connect(self.c, 'body_changed', self._after_body_key)

    def _build_layout(self, show_head=True, show_control=True, update=True, recurse=False):
        """build_layout - build layout
        """
        DBG("build layout")
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)

        # header
        self.header = self._add_frame()
        self.line_edit = QtWidgets.QLineEdit(self)
        self.header.layout().addWidget(self.line_edit)

        # controls
        self.control = self._add_frame()
        # checkboxes
        txt = ",\ncheck to do this always"
        self.cb_track = self._add_checkbox("Track", self.change_track,
            "Track the node selected in the tree"+txt)
        self.cb_goto = self._add_checkbox("Goto", self.change_goto,
            "Make the tree go to this node"+txt)
        self.cb_update = self._add_checkbox("Update", self.change_update,
            "Update view to match changed node"+txt)
        self.cb_recurse = self._add_checkbox("Recurse", self.change_recurse,
            "Recursive view"+txt, checked=recurse)
        # mode menu
        btn = self.btn_mode = QtWidgets.QPushButton("Mode", self)
        self.control.layout().addWidget(btn)
        btn.setContextMenuPolicy(QtConst.CustomContextMenu)
        btn.customContextMenuRequested.connect(  # right click
            lambda pnt: self.mode_menu())
        btn.clicked.connect(  # or left click
            lambda checked: self.mode_menu())

        # misc. menu
        btn = self.control_menu_button = QtWidgets.QPushButton(u"More\u25BE", self)
        self.control.layout().addWidget(btn)
        btn.setContextMenuPolicy(QtConst.CustomContextMenu)
        btn.customContextMenuRequested.connect(  # right click
            lambda pnt: self.misc_menu())
        btn.clicked.connect(  # or left click
            lambda checked: self.misc_menu())

        # padding
        self.control.layout().addItem(
            QtWidgets.QSpacerItem(0, 0, hPolicy=QtWidgets.QSizePolicy.Expanding))

        # content
        self.splitter = QtWidgets.QSplitter(self)
        self.splitter.setOrientation(QtCore.Qt.Vertical)
        self.layout().addWidget(self.splitter)
        self.edit_frame = self._add_frame()
        self.splitter.addWidget(self.edit_frame)
        self.view_frame = self._add_frame()
        self.splitter.addWidget(self.view_frame)

        self.show()

        # debug
        self.line_edit.setText("test")

    def change_goto(self, state, one_shot=False):
        self.goto = one_shot or bool(state)
        self.state_changed()
        self.goto = bool(state)

    def change_recurse(self, state, one_shot=False):
        self.recurse = one_shot or bool(state)
        self.state_changed()
        self.recurse = bool(state)

    def change_track(self, state, one_shot=False):
        self.track = one_shot or bool(state)
        if self.track:
            p = self.c.p
            self.new_position(p)
        self.track = bool(state)

    def change_update(self, state, one_shot=False):
        self.update = one_shot or bool(state)
        if self.update:
            p = self.get_position()
            if p is not None:
                self.new_position(p)
        self.update = bool(state)

    def close(self):
        """close - clean up
        """
        do_close = QtWidgets.QWidget.close(self)
        if do_close:
            sig.disconnect_all(self)
            DBG("unregister handlers\n")
            for hook, handler in self.handlers:
                g.unregisterHandler(hook, handler)
        return do_close

    def edit_widget_focus(self):
        """edit_widget_focus - edit widget got focus"""
        if self.goto:
            self.goto_node()

    def get_position(self):
        """get_position - get current position"""
        return self._find_gnx_node(self.gnx)

    def goto_node(self):
        """goto_node - goto node being edited / viewed"""
        p = self.get_position()
        if p and p != self.c.p:
            self.c.selectPosition(p)

    def load_modules(self):
        """load_modules - load modules to find widgets
        """
        module_dir = os.path.dirname(__file__)
        names = [os.path.splitext(i) for i in os.listdir(module_dir)
                 if os.path.isfile(os.path.join(module_dir, i))]
        modules = []
        for name in [i[0] for i in names if i[1].lower() == '.py']:
            try:
                if g.isPython3:
                    modules.append(import_module('leo.core.editpane.'+name))
                else:
                    exec ( "import %s" % name )  # parens for Python 3 syntax
                    modules.append(locals()[name])
            except ImportError:
                pass

        self.modules = []
        self.widget_classes = []
        for module in modules:
            for key in dir(module):
                value = getattr(module, key)
                if hasattr(value, 'lep_type') and value not in self.widget_classes:
                    if module not in self.modules:
                        self.modules.append(module)
                    self.widget_classes.append(value)

    def misc_menu(self):
        """build menu on Action button"""

        # info needed to separate edit and view widgets in self.widget_classes
        name_test_current = [
            ("Editor", lambda x: x.lep_type == 'EDITOR', self.edit_widget.__class__),
            ("Viewer", lambda x: x.lep_type != 'EDITOR', self.view_widget.__class__),
        ]

        menu = QtWidgets.QMenu()
        for name, is_one, current in name_test_current:
            # list Editor widgets, then Viewer widgets
            for widget_class in [i for i in self.widget_classes if is_one(i)]:
                def cb(checked, widget_class=widget_class):
                    self.set_widget(widget_class=widget_class)
                act = QtWidgets.QAction("%s: %s" % (name, widget_class.lep_name), self)
                act.setCheckable(True)
                act.setChecked(widget_class == current)
                act.triggered.connect(cb)
                menu.addAction(act)
        menu.exec_(self.mapToGlobal(self.control_menu_button.pos()))

    def mode_menu(self):
        """build menu on Action button"""
        menu = QtWidgets.QMenu()

        for mode in 'edit', 'view', 'split':
            act = QtWidgets.QAction(mode.title(), self)
            def cb(checked, self=self, mode=mode):
                self.set_mode(mode)
            act.triggered.connect(cb)
            act.setCheckable(True)
            act.setChecked(mode == self.mode)
            menu.addAction(act)
        menu.exec_(self.mapToGlobal(self.btn_mode.pos()))

    def new_position(self, p):
        """new_position - update editor and view for new Leo position

        :param position p: the new position
        """
        if self.track:
            self.gnx = p.gnx
        else:
            p = self.get_position()

        self.new_position_edit(p)
        self.new_position_view(p)

    def new_position_edit(self, p):
        """new_position_edit - update editor for new position

        WARNING: unlike new_position() this uses p without regard
                 for self.track

        :param position p: the new position
        """

        DBG("new edit position")
        if self.mode != 'view':
            self.edit_widget.new_position(p)

    def new_position_view(self, p):
        """new_position_view - update viewer for new position

        WARNING: unlike new_position() this uses p without regard
                 for self.track

        :param position p: the new position
        """
        DBG("new view position")
        if self.mode != 'edit':
            self.view_widget.new_position(p)

    def text_changed(self, new_text):
        """text_changed - node text changed by this LEP's editor"""

        # Update p.b
        p = self.get_position()
        sig.lock(self)
        p.b = new_text  # triggers 'body_changed' signal from c
        self.update_position_view(p)  # as we're ignoring signals
        sig.unlock(self)
    def update_position(self, p):
        """update_position - update editor and view for current Leo position

        :param position p: the new position
        """
        if self.track:
            self.gnx = p.gnx
        else:
            p = self.get_position()

        self.update_position_edit(p)
        self.update_position_view(p)

    def update_position_edit(self, p):
        """update_position_edit - update editor for current position

        WARNING: unlike update_position() this uses p without regard
                 for self.track

        :param position p: the position to update to
        """

        DBG("update edit position")
        if self.mode != 'view':
            self.edit_widget.update_position(p)

    def update_position_view(self, p):
        """update_position_view - update viewer for current position

        WARNING: unlike update_position() this uses p without regard
                 for self.track

        :param position p: the position to update to
        """

        DBG("update view position")
        if self.mode != 'edit':
            self.view_widget.update_position(p)

    def render(self, checked):
        pass

    def set_widget(self, widget_class=None, lep_type='TEXT'):
        """set_widget - set edit or view widget

        :param QWidget widget: widget to use
        """

        if widget_class is None:
            widget_class = [i for i in self.widget_classes if i.lep_type == lep_type][0]
        if hasattr(widget_class, 'lep_type') and widget_class.lep_type == 'EDITOR':
            frame = self.edit_frame
            attr = 'edit_widget'
            update = self.new_position_edit
        else:
            frame = self.view_frame
            attr = 'view_widget'
            update = self.new_position_view
        widget = widget_class(c=self.c, lep=self)

        setattr(self, attr, widget)
        for i in reversed(range(frame.layout().count())):
            frame.layout().itemAt(i).widget().setParent(None)
        frame.layout().addWidget(widget)
        update(self.get_position())

    def set_mode(self, mode):
        """set_mode - change mode edit / view / split

        :param str mode: mode to change to

        """
        self.mode = mode
        self.btn_mode.setText(u"%s\u25BE" % mode.title())
        self.state_changed()

    def state_changed(self):
        """state_changed - control state has changed
        """

        if self.goto and self.get_position() != self.c.p:
            self.goto_node()

        if self.mode == 'edit':
            self.edit_frame.show()
            self.view_frame.hide()
        elif self.mode == 'view':
            self.edit_frame.hide()
            self.view_frame.show()
        else:
           self.edit_frame.show()
           self.view_frame.show()

        self.update_position(self.c.p)



