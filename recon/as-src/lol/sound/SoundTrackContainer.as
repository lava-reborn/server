class lol.sound.SoundTrackContainer extends lol.sound.SoundContainer
{
   var _cont;
   var _sound;
   var start;
   var t;
   function SoundTrackContainer(name)
   {
      super(name);
   }
   function playSound()
   {
      if(!this._sound)
      {
         this._sound = new Sound(this._cont);
         this._sound.attachSound("track");
      }
      this._sound.onSoundComplete = function()
      {
         this.start(0,0);
      };
      this._sound.stop();
      this._sound.start(0,0);
   }
   function stop()
   {
      this.t.Clear();
      super.stop();
   }
}
