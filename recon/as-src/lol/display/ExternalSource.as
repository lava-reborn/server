class lol.display.ExternalSource
{
   var cont_mc;
   var dispatchEvent;
   var loaded;
   var status;
   function ExternalSource()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.status = null;
      this.loaded = false;
   }
   function loadSource(url)
   {
      if(this.status == null)
      {
         this.status = "loading";
         this.__loadSource(url);
      }
   }
   function __loadSource(url)
   {
   }
   function onLoadSource(target)
   {
      this.loaded = true;
      this.status = "loaded";
      this.dispatchEvent({type:"onLoadSource"});
   }
   function set cont(c_mc)
   {
      if(c_mc)
      {
         this.cont_mc = c_mc;
      }
   }
   function get cont()
   {
      return this.cont_mc;
   }
   function kill()
   {
      this.cont_mc.removeMovieClip();
   }
}
