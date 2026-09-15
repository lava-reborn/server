class lol.utils.MCFabric
{
   function MCFabric()
   {
   }
   static function create(classObject, parent_mc, name, depth, params)
   {
      depth = depth != null ? depth : parent_mc.getNextHighestDepth();
      var _loc1_ = parent_mc.createEmptyMovieClip(name,depth);
      _loc1_.__proto__ = classObject.prototype;
      classObject.apply(_loc1_,params);
      return _loc1_;
   }
}
