class lol.sound.SoundLibrary extends MovieClip
{
   var soundStore;
   static var _lib;
   function SoundLibrary()
   {
      super();
      this.soundStore = new Array();
   }
   static function create(type)
   {
      return new lol.sound.SoundLibrary();
   }
   static function get lib()
   {
      return lol.sound.SoundLibrary._lib;
   }
   function getSound(name)
   {
      return new lol.sound.SoundContainer(name);
   }
}
