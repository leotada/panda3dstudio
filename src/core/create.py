from .base import *


class CreationManager(BaseObject):

    def __init__(self):

        GlobalData.set_default("active_creation_type", "")

        self._creation_start_mouse = (0, 0)
        self._origin_pos = None
        self._interactive_creation_started = False
        self._interactive_creation_ended = False
        self._mode_status = ""
        self._creation_type = ""
        handler = lambda info: setattr(self, "_interactive_creation_ended", True)
        Mgr.add_notification_handler("creation_ended", "creation_mgr", handler)

        status_data = GlobalData["status_data"]
        status_data["create"] = {}

        Mgr.add_app_updater("interactive_creation", self.__update_creation)
        Mgr.add_app_updater("creation", self.__create_object)

        add_state = Mgr.add_state
        add_state("creation_mode", -10, self.__enter_creation_mode, self.__exit_creation_mode)

        def enter_state(prev_state_id, is_active):

            Mgr.do("enable_view_gizmo", False)

        add_state("checking_creation_start", -11, enter_state)

        def cancel_creation():

            Mgr.remove_task("check_creation_start")
            self._interactive_creation_started = False
            self._interactive_creation_ended = True
            Mgr.enter_state("creation_mode")

        bind = Mgr.bind_state
        bind("creation_mode", "create -> navigate", "space",
             lambda: Mgr.enter_state("navigation_mode"))
        bind("creation_mode", "create -> select", "escape",
             lambda: Mgr.exit_state("creation_mode"))
        bind("creation_mode", "exit creation mode", "mouse3",
             lambda: Mgr.exit_state("creation_mode"))
        bind("checking_creation_start", "quit creation", "escape", cancel_creation)
        bind("checking_creation_start", "cancel creation",
             "mouse3", cancel_creation)
        bind("checking_creation_start", "abort creation",
             "mouse1-up", cancel_creation)
        bind("creation_mode", "start object creation", "mouse1",
             self.__start_interactive_creation)

    def __update_creation(self, mode_status):

        if mode_status == "started":

            creation_type = GlobalData["active_creation_type"]

            if self._mode_status != "suspended" or self._creation_type != creation_type:

                Mgr.update_app("selected_obj_types", (creation_type,))
                Mgr.update_remotely("next_obj_name", Mgr.get("next_obj_name", creation_type))
                obj_prop_defaults = Mgr.get("{}_prop_defaults".format(creation_type))

                for prop_id, value in obj_prop_defaults.iteritems():
                    Mgr.update_app("obj_prop_default", creation_type, prop_id, value)

            self._creation_type = creation_type

        elif mode_status == "ended":

            self._creation_type = ""

            selection = Mgr.get("selection")
            count = len(selection)
            type_checker = lambda obj, main_type: obj.get_geom_type() if main_type == "model" else main_type
            obj_types = set(type_checker(obj, obj.get_type()) for obj in selection)
            Mgr.update_app("selected_obj_types", tuple(obj_types))
            Mgr.update_app("selection_count")

            names = OrderedDict()

            for obj in selection:
                names[obj.get_id()] = obj.get_name()

            Mgr.update_remotely("selected_obj_names", names)

            sel_colors = set(obj.get_color() for obj in selection if obj.has_color())
            sel_color_count = len(sel_colors)

            if sel_color_count == 1:
                color = sel_colors.pop()
                color_values = [x for x in color][:3]
                Mgr.update_remotely("selected_obj_color", color_values)

            Mgr.update_app("sel_color_count")

            if count == 1:

                obj = selection[0]
                obj_type = obj_types.pop()

                for prop_id in obj.get_type_property_ids():
                    value = obj.get_property(prop_id, for_remote_update=True)
                    Mgr.update_remotely("selected_obj_prop", obj_type, prop_id, value)

        self._mode_status = mode_status

    def __enter_creation_mode(self, prev_state_id, is_active):

        Mgr.do("enable_view_gizmo")

        if GlobalData["active_obj_level"] != "top":
            GlobalData["active_obj_level"] = "top"
            Mgr.update_app("active_obj_level")

        if self._interactive_creation_ended:

            self._interactive_creation_ended = False

        else:

            GlobalData["active_transform_type"] = ""
            Mgr.update_app("active_transform_type", "")
            Mgr.update_app("interactive_creation", "started")
            Mgr.set_cursor("create")

        creation_type = GlobalData["active_creation_type"]
        Mgr.update_app("status", ["create", creation_type, "idle"])

    def __exit_creation_mode(self, next_state_id, is_active):

        if self._interactive_creation_started:

            self._interactive_creation_started = False

        else:

            Mgr.set_cursor("main")

            if is_active:
                mode_status = "suspended"
            else:
                mode_status = "ended"
                GlobalData["active_creation_type"] = ""

            Mgr.update_app("interactive_creation", mode_status)

    def __check_creation_start(self, task):

        mouse_pointer = Mgr.get("mouse_pointer", 0)
        mouse_x = mouse_pointer.get_x()
        mouse_y = mouse_pointer.get_y()
        mouse_start_x, mouse_start_y = self._creation_start_mouse

        if max(abs(mouse_x - mouse_start_x), abs(mouse_y - mouse_start_y)) > 3:
            object_type = GlobalData["active_creation_type"]
            Mgr.do("start_{}_creation".format(object_type), self._origin_pos)
            return task.done

        return task.cont

    def __start_interactive_creation(self):

        if not self.mouse_watcher.has_mouse():
            return

        mouse_pos = self.mouse_watcher.get_mouse()
        self._origin_pos = Mgr.get(("grid", "point_at_screen_pos"), mouse_pos)

        if not self._origin_pos:
            return

        mouse_pointer = Mgr.get("mouse_pointer", 0)
        mouse_x = mouse_pointer.get_x()
        mouse_y = mouse_pointer.get_y()
        self._creation_start_mouse = (mouse_x, mouse_y)
        self._interactive_creation_started = True
        self._interactive_creation_ended = False

        Mgr.enter_state("checking_creation_start")
        Mgr.add_task(self.__check_creation_start, "check_creation_start", sort=3)

    def __create_object(self, pos_id):

        if pos_id == "grid_pos":
            origin_pos = Point3()
        elif pos_id == "cam_target_pos":
            grid_origin = Mgr.get(("grid", "origin"))
            origin_pos = self.cam.target.get_pos(grid_origin)

        object_type = GlobalData["active_creation_type"]
        process = Mgr.do("create_{}".format(object_type), origin_pos)

        if process.next():
            descr = "Creating {}...".format(object_type)
            Mgr.do_gradually(process, "creation", descr, cancellable=True)


MainObjects.add_class(CreationManager)
