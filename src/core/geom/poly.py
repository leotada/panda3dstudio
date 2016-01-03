from ..base import *


class PolygonManager(ObjectManager, PickingColorIDManager):

    def __init__(self):

        ObjectManager.__init__(
            self, "poly", self.__create_polygon, "sub", pickable=True)
        PickingColorIDManager.__init__(self)
        PickableTypes.add("poly")

    def __create_polygon(self, geom_data_obj, triangle_data, edges, verts):

        poly_id = self.get_next_id()
        picking_col_id = self.get_next_picking_color_id()
        polygon = Polygon(poly_id, picking_col_id,
                          geom_data_obj, triangle_data, edges, verts)

        return polygon, picking_col_id


class Polygon(BaseObject):

    def __getstate__(self):

        # When pickling a Polygon, it should not have a GeomDataObject, since this
        # will be pickled separately.

        d = self.__dict__.copy()
        d["_geom_data_obj"] = None

        return d

    def __init__(self, poly_id, picking_col_id, geom_data_obj, triangle_data, edges, verts):

        self._type = "poly"
        self._id = poly_id
        self._picking_col_id = picking_col_id
        self._geom_data_obj = geom_data_obj
        self._creation_time = None
        self._prev_prop_time = {"tri_data": None}
        self._tri_data = triangle_data  # sequence of 3-tuples of vertex IDs
        self._vert_ids = [vert.get_id() for vert in verts]
        self._edge_ids = [edge.get_id() for edge in edges]

        for vert in verts:
            vert.set_polygon_id(poly_id)

        for edge in edges:
            edge.set_polygon_id(poly_id)

        self._center_pos = Point3()
        self._normal = Vec3()

    def __getitem__(self, index):

        try:
            return self._tri_data[index]
        except IndexError:
            raise IndexError("Index out of range.")
        except TypeError:
            raise TypeError("Index must be an integer value.")

    def __len__(self):
        """
        Return the size of the polygon as the number of data rows of the associated
        GeomTriangles object.
        Note that this is NOT the same as the number of vertices belonging to this
        polygon! Use Polygon.get_vertex_count() for this.

        """

        return len(self._tri_data) * 3

    def get_type(self):

        return self._type

    def get_id(self):

        return self._id

    def get_picking_color_id(self):

        return self._picking_col_id

    def set_geom_data_object(self, geom_data_obj):

        self._geom_data_obj = geom_data_obj

    def get_geom_data_object(self):

        return self._geom_data_obj

    def get_toplevel_object(self):

        return self._geom_data_obj.get_toplevel_object()

    def get_merged_object(self):

        return self

    def set_creation_time(self, time_id):

        self._creation_time = time_id

    def get_creation_time(self):

        return self._creation_time

    def set_previous_property_time(self, prop_id, time_id):

        self._prev_prop_time[prop_id] = time_id

    def get_previous_property_time(self, prop_id):

        return self._prev_prop_time[prop_id]

    def set_triangle_data(self, triangle_data):

        self._tri_data = triangle_data

    def get_vertex_ids(self, in_winding_order=False):

        if not in_winding_order:
            return self._vert_ids

        """
    Return the IDs of the vertices belonging to this polygon, in an order that
    can be used to define the winding of a new triangulation, consistent
    with the winding direction of the existing triangles.

    """

        tri_data = self._tri_data
        tri_sides = {}
        vert_ids = []

        for tri_vert_ids in tri_data:

            for i in range(3):

                side_vert1_id = tri_vert_ids[i]
                side_vert2_id = tri_vert_ids[i - 2]
                tri_side = (side_vert1_id, side_vert2_id)
                tri_side_reversed = tri_side[::-1]

                if tri_side_reversed in tri_sides.get(side_vert2_id, ()):
                    tri_sides[side_vert2_id].remove(tri_side_reversed)
                else:
                    tri_sides.setdefault(side_vert1_id, []).append(tri_side)

        side_vert1_id, tri_side_list = tri_sides.popitem()
        vert_ids.append(side_vert1_id)
        side_vert2_id = tri_side_list[0][1]

        while tri_sides:
            tri_side_list = tri_sides.pop(side_vert2_id)
            side_vert1_id, side_vert2_id = tri_side_list[0]
            vert_ids.append(side_vert1_id)

        return vert_ids

    def get_edge_ids(self):

        return self._edge_ids

    def get_vertices(self):

        verts = self._geom_data_obj.get_subobjects("vert")

        return [verts[vert_id] for vert_id in self._vert_ids]

    def get_edges(self):

        edges = self._geom_data_obj.get_subobjects("edge")

        return [edges[edge_id] for edge_id in self._edge_ids]

    def get_vertex_count(self):

        return len(self._vert_ids)

    def get_row_indices(self):

        verts = self._geom_data_obj.get_subobjects("vert")

        return [verts[vert_id].get_row_index() for vert_id in self._vert_ids]

    def get_triangle_normal(self, triangle_index):

        verts = self._geom_data_obj.get_subobjects("vert")
        tri_verts = [verts[vert_id]
                     for vert_id in self._tri_data[triangle_index]]
        pos1, pos2, pos3 = [vert.get_pos() for vert in tri_verts]

        return V3D(pos2 - pos1) ** V3D(pos3 - pos2)

    def update_normal(self):

        tri_count = len(self._tri_data)
        normals = [self.get_triangle_normal(i) for i in xrange(tri_count)]
        self._normal = sum(normals, Vec3()) / tri_count

    def get_normal(self, ref_node=None):

        if ref_node:
            origin = self._geom_data_obj.get_origin()
            return ref_node.get_relative_vector(origin, self._normal)

        return self._normal

    def get_special_selection(self):

        if Mgr.get_global("sel_polys_by_smoothing"):
            return self._geom_data_obj.get_smoothed_polys(self._id)

        return [self]

    def update_center_pos(self):

        verts = self.get_vertices()
        positions = [vert.get_pos() for vert in verts]
        self._center_pos = sum(positions, Point3()) / len(positions)

    def set_center_pos(self, center_pos):

        self._center_pos = center_pos

    def get_center_pos(self, ref_node):

        origin = self._geom_data_obj.get_origin()
        pos = ref_node.get_relative_point(origin, self._center_pos)

        return pos

    def get_point_at_screen_pos(self, screen_pos):

        ref_node = self.world
        far_point_local = Point3()
        self.cam_lens.extrude(screen_pos, Point3(), far_point_local)
        far_point = ref_node.get_relative_point(self.cam, far_point_local)
        cam_pos = self.cam.get_pos(ref_node)

        plane = Plane(self.get_normal(ref_node), self.get_center_pos(ref_node))
        intersection_point = Point3()

        if not plane.intersects_line(intersection_point, cam_pos, far_point):
            return

        return intersection_point

    def is_facing_camera(self):

        verts = self._geom_data_obj.get_subobjects("vert")

        for vert_ids in self._tri_data:

            plane = Plane(*[verts[vert_id].get_pos(self.world)
                            for vert_id in vert_ids])

            if plane.dist_to_plane(self.cam.get_pos(self.world)) > 0.:
                return True

        return False


MainObjects.add_class(PolygonManager)