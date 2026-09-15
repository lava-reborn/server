class lol.sound.SoundTrackLibrary extends lol.sound.SoundLibrary
{
   var createEmptyMovieClip;
   var getNextHighestDepth;
   var soundStore;
   static var _lib;
   function SoundTrackLibrary()
   {
      super();
   }
   static function create(type)
   {
      if(!lol.sound.SoundTrackLibrary._lib)
      {
         lol.sound.SoundTrackLibrary._lib = lol.sound.SoundTrackLibrary(lol.utils.MCFabric.create(lol.sound.SoundTrackLibrary,_root,"soundLibrary" + type,_root.getNextHighestDepth()));
         return lol.sound.SoundTrackLibrary._lib;
      }
   }
   function getSound(name)
   {
      var _loc3_;
      if(!this.soundStore[name])
      {
         _loc3_ = new lol.sound.SoundTrackContainer(name);
         this.soundStore[name] = _loc3_;
         _loc3_.cont = this.createEmptyMovieClip(name,this.getNextHighestDepth());
      }
      return this.soundStore[name];
   }
}
