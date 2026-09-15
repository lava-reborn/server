class lol.sound.SoundTLContainer extends lol.sound.SoundContainer
{
   var _cont;
   var _sound;
   function SoundTLContainer(name)
   {
      super(name);
   }
   function onSoundLoaded(target_mc)
   {
      super.onSoundLoaded(target_mc);
      this.playSound();
   }
   function playSound()
   {
      if(lol.gpui.UserSettings.getSetting("gameSoundVolume") > 0)
      {
         if(!this._sound)
         {
            this._sound = new Sound(this._cont);
         }
         this._cont.gotoAndPlay(2);
      }
   }
}
