class lol.sound.SoundTLLibrary extends lol.sound.SoundLibrary
{
   var createEmptyMovieClip;
   var getNextHighestDepth;
   var soundStore;
   static var _lib;
   function SoundTLLibrary()
   {
      super();
   }
   static function create(type)
   {
      if(!lol.sound.SoundTLLibrary._lib)
      {
         lol.sound.SoundTLLibrary._lib = lol.sound.SoundTLLibrary(lol.utils.MCFabric.create(lol.sound.SoundTLLibrary,_root,"soundLibrary" + type,_root.getNextHighestDepth()));
         return lol.sound.SoundTLLibrary._lib;
      }
   }
   function getSound(name)
   {
      var _loc3_;
      if(!this.soundStore[name])
      {
         _loc3_ = new lol.sound.SoundTLContainer(name);
         this.soundStore[name] = _loc3_;
         _loc3_.cont = this.createEmptyMovieClip(name,this.getNextHighestDepth());
      }
      return this.soundStore[name];
   }
}
