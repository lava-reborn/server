class lol.display.SourceLibrary extends MovieClip
{
   var sourcestore_arr;
   var store_arr;
   static var _lib;
   static var SPRITE = "sprite";
   static var LIBRARY = "lib";
   function SourceLibrary()
   {
      super();
      lol.events.LEventDispatcher.initialize(this);
      this.store_arr = new Array();
      this.sourcestore_arr = new Array();
   }
   static function getSource(name, type)
   {
      if(!lol.display.SourceLibrary._lib.store_arr[name])
      {
         return lol.display.SourceLibrary.createNewSource(name,type);
      }
      return lol.display.SourceLibrary._lib.store_arr[name];
   }
   static function createNewSource(name, typ)
   {
      var _loc3_ = !typ ? lol.display.SourceLibrary.SPRITE : typ;
      var _loc1_;
      if(_loc3_ == lol.display.SourceLibrary.SPRITE)
      {
         _loc1_ = new lol.display.SpriteSource();
      }
      else
      {
         if(_loc3_ != lol.display.SourceLibrary.LIBRARY)
         {
            return null;
         }
         _loc1_ = new lol.display.LibSource();
      }
      var _loc2_ = lol.display.SourceLibrary._lib.getNextHighestDepth();
      if(_loc3_ == lol.display.SourceLibrary.LIBRARY)
      {
         _loc1_.cont = lol.display.DisplaySprite.create(lol.display.SourceLibrary._lib,"bgd" + _loc2_,_loc2_);
      }
      else
      {
         _loc1_.cont = lol.display.AnimationSprite.create(lol.display.SourceLibrary._lib,"bgd" + _loc2_,_loc2_);
      }
      _loc1_.sourceName = name;
      lol.display.SourceLibrary._lib.store_arr[name] = _loc1_;
      return _loc1_;
   }
   static function clearSource(name)
   {
      var _loc1_ = lol.display.ExternalSource(lol.display.SourceLibrary._lib.store_arr[name]);
      _loc1_.kill();
      lol.display.SourceLibrary._lib.store_arr[name] = null;
   }
   static function getSound(name)
   {
      return lol.display.SourceLibrary._lib.store_arr[name].getSound();
   }
   static function playSound(name, offset, loop)
   {
      return lol.display.SourceLibrary._lib.store_arr[name].playSound(offset,loop);
   }
   static function get lib()
   {
      return lol.display.SourceLibrary._lib;
   }
   static function set lib(§null§)
   {
   }
   static function create()
   {
      if(!lol.display.SourceLibrary._lib)
      {
         lol.display.SourceLibrary._lib = lol.display.SourceLibrary(lol.utils.MCFabric.create(lol.display.SourceLibrary,_root,"sourceLibrary",-1));
         lol.display.SourceLibrary._lib._y = 1800;
      }
   }
}
