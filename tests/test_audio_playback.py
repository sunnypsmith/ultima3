"""Exercise native effects and music scheduling without opening an audio device.

The harness compiles the current implementation with a silent AVAudioPlayer
substitute. AVAudioFile still decodes real synthetic PCM fixtures. Requires the
macOS command-line developer tools; other platforms skip these native tests.
"""

from pathlib import Path
import platform
import plistlib
import shutil
import struct
import subprocess
import tempfile
import unittest
import wave


ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>
#import <Carbon/Carbon.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
static int createdPlayers, stoppedPlayers, musicCalls;
static bool headless, hasSurface = true, quitOnPump;
static uint32_t fakeTick;
Boolean gDone;
static short sQTSoundVolume = 100;
static NSMutableDictionary *sEffectSounds;
static NSMutableArray *sEffectPlayers;
Boolean U3CocoaIsHeadlessDiagnostic(void) { return headless; }
Boolean U3CocoaHasMainSurface(void) { return hasSurface; }
void U3CocoaPumpEvents(void) { if (quitOnPump) gDone = true; }
uint32_t U3PlatformTickCount(void) { return fakeTick; }
static void U3ServiceNativeMusic(void);
void U3AudioUpdateMusic(void) { ++musicCalls; U3ServiceNativeMusic(); }
static void check(bool ok, const char *message) {
    if (!ok) { fprintf(stderr, "FAIL: %s\n", message); exit(1); }
}
@interface U3SilentPlayer : NSObject {
    BOOL _playing;
    float _volume;
    NSTimeInterval _duration, _currentTime;
}
@property float volume;
@property NSTimeInterval duration, currentTime;
@property (readonly, getter=isPlaying) BOOL playing;
- (id)initWithContentsOfURL:(NSURL *)url error:(NSError **)error;
- (BOOL)prepareToPlay;
- (BOOL)play;
- (void)stop;
@end
@implementation U3SilentPlayer
@synthesize volume = _volume, duration = _duration, currentTime = _currentTime;
- (id)initWithContentsOfURL:(NSURL *)url error:(NSError **)error {
    if ((self = [super init])) {
        AVAudioFile *file = [[AVAudioFile alloc] initForReading:url error:error];
        if (!file) { [self release]; return nil; }
        _duration = file.length / file.processingFormat.sampleRate;
        [file release]; ++createdPlayers;
    }
    return self;
}
- (BOOL)isPlaying { return _playing; }
- (BOOL)prepareToPlay { return YES; }
- (BOOL)play { _playing = YES; return YES; }
- (void)stop { _playing = NO; ++stoppedPlayers; }
@end
#define AVAudioPlayer U3SilentPlayer
/* EFFECTS_IMPLEMENTATION */
/* MUSIC_SERVICE_IMPLEMENTATION */
int main(void) {
 @autoreleasepool {
    check(fabs(U3EffectGainForURL(U3EffectURL(@"quiet")) - 1) < 0.0001, "quiet PCM must not be boosted");
    check(fabs(U3EffectGainForURL(U3EffectURL(@"silence")) - 1) < 0.0001, "silence gain finite/unity");
    check(fabs(U3EffectGainForURL(U3EffectURL(@"loud")) - pow(10, -16.0/20) / 0.8) < 0.001, "loud PCM RMS target");
    check(fabs(U3EffectGainForURL(U3EffectURL(@"impulse")) - pow(10, -3.0/20)) < 0.001, "transient peak headroom");
    PlaySoundFileQT(CFSTR("quiet"), true);
    check(createdPlayers == 1 && sEffectPlayers.count == 1, "first effect creates one player");
    PlaySoundFileQT(CFSTR("quiet"), true);
    check(createdPlayers == 1, "rapid repeats are coalesced");
    U3EffectSound *quiet = [sEffectSounds objectForKey:@"quiet"];
    quiet->lastStarted = 0;
    PlaySoundFileQT(CFSTR("quiet"), true);
    check(quiet->players.count == 2, "short effect can overlap twice");
    quiet->lastStarted = 0;
    PlaySoundFileQT(CFSTR("quiet"), true);
    check(quiet->players.count == 2, "per-effect voice limit");
    [[quiet->players objectAtIndex:0] stop]; quiet->lastStarted = 0;
    PlaySoundFileQT(CFSTR("quiet"), true);
    check(createdPlayers == 2, "finished player is reused");
    SetSoundVolumePercent(25);
    for (U3SilentPlayer *player in quiet->players)
        check(fabs(player.volume - quiet->gain * 0.25) < 0.0001, "volume updates cached players");
    SetSoundVolumePercent(0);
    NSUInteger cached = sEffectSounds.count;
    PlaySoundFileQT(CFSTR("loud"), true);
    check(sEffectSounds.count == cached, "mute skips decoding and new playback");
    SetSoundVolumePercent(-20); check(sQTSoundVolume == 0, "negative volume clamps to mute");
    SetSoundVolumePercent(150); check(sQTSoundVolume == 100, "excess volume clamps to unity");
    SetSoundVolumePercent(100);
    PlaySoundFileQT(CFSTR("long"), true);
    U3EffectSound *longEffect = [sEffectSounds objectForKey:@"long"];
    longEffect->lastStarted = 0; PlaySoundFileQT(CFSTR("long"), true);
    check(longEffect->players.count == 1, "long effects do not stack");
    for (int i = 0; i < 10; ++i) {
        NSString *name = [NSString stringWithFormat:@"voice%d", i];
        PlaySoundFileQT((CFStringRef)name, true);
        check(sEffectPlayers.count <= 8, "global voice count is bounded");
    }
    check(stoppedPlayers > 1, "global cap stops old voices");
    U3CocoaCloseSoundEffects();
    check(!sEffectSounds && !sEffectPlayers, "closing releases caches");
    quitOnPump = true;
    PlaySoundFileQT(CFSTR("long"), false);
    U3EffectSound *interrupted = sEffectSounds[@"long"];
    check(gDone && interrupted && ![[interrupted->players objectAtIndex:0] isPlaying],
          "quit stops a synchronous effect instead of waiting for its duration");
    NSUInteger playersAtQuit = createdPlayers;
    PlaySoundFileQT(CFSTR("quiet"), true);
    check(createdPlayers == playersAtQuit, "no effects start after quit");
    gDone = false; quitOnPump = false;
    U3CocoaCloseSoundEffects();
    headless = true; PlaySoundFileQT(CFSTR("quiet"), true);
    check(!sEffectSounds && !sEffectPlayers, "diagnostics never create players");
    fakeTick = 100; U3ServiceNativeMusic(); check(musicCalls == 0, "headless music skip");
    headless = false; hasSurface = false; U3ServiceNativeMusic(); check(musicCalls == 0, "missing surface music skip");
    hasSurface = true; gDone = true; U3ServiceNativeMusic(); check(musicCalls == 0, "quit music skip");
    gDone = false; U3ServiceNativeMusic(); check(musicCalls == 1, "first update and recursive reentry guard");
    fakeTick = 102; U3ServiceNativeMusic(); check(musicCalls == 1, "music throttle");
    fakeTick = 103; U3ServiceNativeMusic(); check(musicCalls == 2, "music resumes at three ticks");
    fakeTick = UINT32_MAX - 1; U3ServiceNativeMusic(); check(musicCalls == 3, "clock near wrap");
    fakeTick = 1; U3ServiceNativeMusic(); check(musicCalls == 4, "unsigned tick wrap");
    puts("Silent effects gain/cache/voice/volume and native music-service tests passed");
 }
 return 0;
}
'''


def function_source(source, signature):
    start = source.index(signature)
    body = source.index("{", start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


@unittest.skipUnless(platform.system() == "Darwin" and shutil.which("clang"),
                     "Native silent harness requires macOS developer tools")
class AudioPlaybackTests(unittest.TestCase):
    def test_silent_native_playback_policy(self):
        cocoa = (ROOT / "Sources/CocoaBridge.m").read_text()
        effects = cocoa[cocoa.index("static float U3EffectGainForURL"):
                        cocoa.index("int RunCocoaDialog(")]
        service = function_source((ROOT / "Sources/U3PlatformLegacy.m").read_text(),
                                  "static void U3ServiceNativeMusic(void)")
        with tempfile.TemporaryDirectory(prefix="u3-silent-audio-") as temporary:
            base = Path(temporary)
            contents = base / "AudioTests.app/Contents"
            assets = contents / "Resources/SoundsPCM"
            assets.mkdir(parents=True)
            executable = contents / "MacOS/AudioTests"
            executable.parent.mkdir()
            (contents / "Info.plist").write_bytes(plistlib.dumps({
                "CFBundleExecutable": "AudioTests", "CFBundleIdentifier": "local.u3.silent-audio-tests",
                "CFBundlePackageType": "APPL",
            }))
            fixtures = {"quiet": [655] * 800, "loud": [26214] * 800,
                        "silence": [0] * 800, "impulse": [32767] + [0] * 799,
                        "long": [655] * 8000}
            fixtures.update({f"voice{i}": [655] * 800 for i in range(10)})
            for name, samples in fixtures.items():
                with wave.open(str(assets / (name + ".wav")), "wb") as output:
                    output.setparams((1, 2, 8000, len(samples), "NONE", "not compressed"))
                    output.writeframes(struct.pack("<" + "h" * len(samples), *samples))
            source = base / "harness.m"
            source.write_text(HARNESS.replace("/* EFFECTS_IMPLEMENTATION */", effects)
                              .replace("/* MUSIC_SERVICE_IMPLEMENTATION */", service))
            compiled = subprocess.run(
                ["clang", "-fsanitize=address,undefined", "-g", "-Wno-deprecated-declarations", str(source), "-framework", "Foundation",
                 "-framework", "AVFoundation", "-framework", "Carbon", "-o", str(executable)],
                capture_output=True, text=True, timeout=45,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            checked = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("tests passed", checked.stdout)


if __name__ == "__main__":
    unittest.main()
