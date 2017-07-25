import AlteryxPythonSDK as Sdk
import xml.etree.ElementTree as Et


class AyxPlugin:
    def __init__(self, n_tool_id, alteryx_engine, generic_engine, output_anchor_mgr):
        """Initialize members that will be used"""
        # miscellaneous variables
        self.n_tool_id = n_tool_id
        self.name = str('PyUnique_') + str(self.n_tool_id)
        self.initialized = False
        self.field_selection = None
        self.field_index = 0
        self.key_set_current = set()
        self.key_set_previous = set()
        self.key_set_previous_len = 0

        # engine handles
        self.alteryx_engine = alteryx_engine
        self.generic_engine = generic_engine

        # output anchor management
        self.output_anchor_mgr = output_anchor_mgr
        self.target_output_anchor = None
        self.unique_output_anchor = None
        self.dupe_output_anchor = None

        # record management
        self.record_info_in = None
        self.record_info_out = None
        self.record_creator = None
        self.record_copier = None
        pass

    def output_message(self, method, status, message):
        """Notifies the Alteryx engine of any message generated by a tool."""
        self.alteryx_engine.output_message(self.n_tool_id, status, method + ': ' + str(message))
        return

    def pi_init(self, str_xml):
        """Called when the Alteryx engine is ready to provide the tool configuration from the GUI."""
        try:  # retrieving user's field selection
            self.field_selection = Et.fromstring(str_xml).find('FieldSelect').text
        except AttributeError:
            self.output_message('pi_init', Sdk.EngineMessageType.error, 'Invalid XML: ' + str_xml)
            raise
        self.unique_output_anchor = self.output_anchor_mgr.get_output_anchor('Unique')
        self.dupe_output_anchor = self.output_anchor_mgr.get_output_anchor('Duplicate')
        pass

    def pi_close(self, b_has_errors):
        """Called prior to the destruction of the tool object represented by the plugin,
        once all records have been processed."""
        pass

    def pi_add_incoming_connection(self, str_type, str_name):
        """Called when the Alteryx engine is attempting to add an incoming data connection."""
        return self

    def pi_add_outgoing_connection(self, str_name):
        """Called when the Alteryx engine is attempting to add an outgoing data connection."""
        return True

    def pi_push_all_records(self, n_record_limit):
        """Called when the Alteryx engine when it's expecting the plugin to provide all of its data."""
        self.output_message('pi_push_all_records', Sdk.EngineMessageType.error, 'Missing Incoming Connection')
        return False

    def ii_init(self, record_info_in):
        """Called when the incoming connection's record metadata is available or has changed, and
        has let the Alteryx engine know what its output will look like. """
        self.record_info_in = record_info_in
        self.record_info_out = record_info_in

        # initialize unique_output_anchor
        self.unique_output_anchor.init(self.record_info_out)

        # initialize dupe_output_anchor
        self.dupe_output_anchor.init(self.record_info_out)

        self.record_creator = self.record_info_out.construct_record_creator()

        # Setting the record_copier to copy the metadata from the input records into new output records
        self.record_copier = Sdk.RecordCopier(self.record_info_out, self.record_info_in)

        for idx in range(len(self.record_info_in)):  # For each field
            self.record_copier.add(idx, idx)
        self.record_copier.done_adding()
        self.initialized = True
        self.field_index = self.record_info_in.get_field_num(self.field_selection)
        return True

    def set_key_set_previous_len(self, key_set_current):
        self.key_set_previous = key_set_current
        self.key_set_previous_len = len(self.key_set_previous)
        pass

    def set_output_direction(self, key_set_current):
        """Evaluates incremental changes in set lengths, to decide
        which output anchor to have the incoming record be pushed to"""

        # if a new unique record has been added, set target output anchor as the unique output anchor
        if len(key_set_current) > self.key_set_previous_len:
            self.target_output_anchor = self.unique_output_anchor
        else:
            self.target_output_anchor = self.dupe_output_anchor
        pass

    def ii_push_record(self, in_record):
        """Responsible for pushing records out, with a count limit set by the user in n_record_select,
        called when an input record is being sent to the plugin."""
        if not self.initialized:
            return False
        self.record_creator.reset()
        self.record_copier.copy(self.record_creator, in_record)
        out_record = self.record_creator.finalize_record()

        # Append the incoming record to the current set
        self.key_set_current.add(self.record_info_in[self.field_index].get_as_string(in_record))

        # Pass the current set to decide which output anchor to push the record to
        self.set_output_direction(self.key_set_current)

        # Update previous set's length
        self.set_key_set_previous_len(self.key_set_current)

        return self.target_output_anchor.push_record(out_record)

    def ii_update_progress(self, d_percent):
        """Called when the incoming connection is requesting that the plugin update its progress."""
        self.alteryx_engine.output_tool_progress(self.n_tool_id, d_percent)
        self.unique_output_anchor.update_progress(d_percent)
        self.dupe_output_anchor.update_progress(d_percent)
        pass

    def ii_close(self):
        """Called when the incoming connection has finished passing all of its records."""
        self.unique_output_anchor.close()
        self.dupe_output_anchor.close()
        pass
