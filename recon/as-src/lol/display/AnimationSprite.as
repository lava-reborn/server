class lol.display.AnimationSprite extends lol.display.DisplaySprite
{
   var createEmptyMovieClip;
   var dispatchEvent;
   var display_mc;
   var mcl_list;
   var src;
   function AnimationSprite()
   {
      super();
   }
   function DisplaySprite()
   {
      lol.events.LEventDispatcher.initialize(this);
   }
   function display(name, url)
   {
      this.display_mc = this.createEmptyMovieClip("display_mc",0);
      var _loc2_ = new MovieClipLoader();
      this.mcl_list = new Object();
      this.mcl_list.onLoadInit = mx.utils.Delegate.create(this,this.onLoadSource);
      _loc2_.addListener(this.mcl_list);
      _loc2_.loadClip(url,this.display_mc);
   }
   function onLoadSource(obj)
   {
      this.src.removeEventListener("onLoadSource",this);
      this.dispatchEvent({type:"onLoadSource"});
   }
   static function create(parent_mc, name, depth, params)
   {
      var _loc1_ = lol.display.AnimationSprite(lol.utils.MCFabric.create(lol.display.AnimationSprite,parent_mc,name,depth,params));
      return _loc1_;
   }
}
