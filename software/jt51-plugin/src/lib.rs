
#[macro_use]
extern crate vst;
extern crate midly;

use vst::api;
use vst::event::{Event, MidiEvent};
use vst::buffer::{AudioBuffer, SendEventBuffer};
use vst::plugin::{CanDo, HostCallback, Info, Plugin};

use midly::{live::LiveEvent, MidiMessage};

plugin_main!(MyPlugin); // Important!

#[derive(Default)]
struct MyPlugin {
    host: HostCallback,
    recv_buffer: SendEventBuffer,
    send_buffer: SendEventBuffer,
}

impl MyPlugin {
    fn send_midi(&mut self) {
        self.send_buffer
            .send_events(self.recv_buffer.events().events(), &mut self.host);
        self.recv_buffer.clear();
    }
}

impl Plugin for MyPlugin {
    fn new(host: HostCallback) -> Self {
        MyPlugin {
            host,
            ..Default::default()
        }
    }

    fn get_info(&self) -> Info {
        Info {
            name: "JT51Plugin".to_string(),
            vendor: "Hans Baier".to_string(),
            unique_id: 19750001,
            ..Default::default()
        }
    }

    fn process_events(&mut self, events: &api::Events) {
        let mut result: Vec<MidiEvent> = vec![];

        for event in events.events() {
            match event {
                Event::Midi(ev) => {
                    let live_event = LiveEvent::parse(&ev.data).unwrap();
                    match live_event {
                        LiveEvent::Midi { channel: _, message } => match message {
                            MidiMessage::NoteOn { key: _, vel: _ } | MidiMessage::NoteOff { key: _, vel: _ } => {
                                let note1 = MidiEvent {
                                    data: [ev.data[0], ev.data[1] + 4, ev.data[2]],
                                    ..ev
                                };
                                let note2 = MidiEvent {
                                    data: [ev.data[0], ev.data[1] + 8, ev.data[2]],
                                    ..ev
                                };
                                result.push(ev);
                                result.push(note1);
                                result.push(note2);
                            }
                            _ => ()
                        }
                        _ => ()
                    }
                }
                _ => ()
            }
        }

        self.recv_buffer.store_events(result);
    }

    fn process(&mut self, buffer: &mut AudioBuffer<f32>) {
        for (input, output) in buffer.zip() {
            for (in_sample, out_sample) in input.iter().zip(output) {
                *out_sample = *in_sample;
            }
        }
        self.send_midi();
    }

    fn process_f64(&mut self, buffer: &mut AudioBuffer<f64>) {
        for (input, output) in buffer.zip() {
            for (in_sample, out_sample) in input.iter().zip(output) {
                *out_sample = *in_sample;
            }
        }
        self.send_midi();
    }

    fn can_do(&self, can_do: CanDo) -> vst::api::Supported {
        use vst::api::Supported::*;
        use vst::plugin::CanDo::*;

        match can_do {
            SendEvents | SendMidiEvent | ReceiveEvents | ReceiveMidiEvent => Yes,
            _ => No,
        }
    }
}
